"""
API 路由
"""
import io
import os
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, jsonify, send_file
from app import db
from app.models import Lead, Config, SearchTask
from app.services.llm import LLMClient, parse_product_description, score_lead
from app.services.search import LinkedInSearcher as Searcher

api_bp = Blueprint('api', __name__)


executor = ThreadPoolExecutor(max_workers=2)


def _clamp_score(value, default=50):
    try:
        score = int(float(value))
    except Exception:
        score = default
    return max(0, min(100, score))


def _fallback_score_lead(lead_data, icp):
    text = " ".join(
        [
            str(lead_data.get("name", "")),
            str(lead_data.get("company", "")),
            str(lead_data.get("bio", "")),
        ]
    ).lower()
    roles = [str(role).strip().lower() for role in (icp.get("target_role") or [])]

    buyer_keywords = [
        "buyer",
        "procurement",
        "purchasing",
        "sourcing",
        "importer",
        "wholesaler",
        "distributor",
        "retail",
        "ecommerce",
        "reseller",
    ]
    supplier_keywords = ["manufacturer", "factory", "oem", "supplier", "producer"]

    score = 25
    tags = []
    if any(word in text for word in buyer_keywords):
        score += 35
        tags.append("buyer_intent")
    if roles and any(role in text for role in roles):
        score += 20
        tags.append("role_match")
    if lead_data.get("email"):
        score += 10
        tags.append("has_email")
    if lead_data.get("url"):
        score += 5
    if any(word in text for word in supplier_keywords):
        score -= 25
        tags.append("possible_supplier")

    score = _clamp_score(score)
    is_target = score >= 65
    priority = "high" if score >= 80 else ("medium" if score >= 60 else "low")
    return {
        "is_target": is_target,
        "score": score,
        "reason": "fallback_rule_score",
        "tags": tags,
        "contact_priority": priority,
    }


def _build_scoring_client():
    provider = (Config.get("default_llm") or os.getenv("DEFAULT_LLM") or "deepseek").strip().lower()
    api_key = (Config.get("api_key") or "").strip() or None
    try:
        client = LLMClient(provider=provider, api_key=api_key)
    except Exception:
        return None
    if not client.api_key:
        return None
    return client


def _score_lead_with_fallback(lead_data, icp, llm_client=None):
    if llm_client is not None:
        try:
            result = score_lead(lead_data, icp, llm=llm_client)
            return {
                "is_target": result.get("is_target"),
                "score": _clamp_score(result.get("score")),
                "reason": str(result.get("reason", "")),
                "tags": result.get("tags", []) or [],
                "contact_priority": str(result.get("contact_priority", "medium")),
            }
        except Exception:
            pass
    return _fallback_score_lead(lead_data, icp)

@api_bp.route('/config', methods=['GET'])
def get_config():
    """获取所有配置"""
    configs = Config.query.all()
    return jsonify({c.key: c.value for c in configs})


@api_bp.route('/config', methods=['POST'])
def set_config():
    """设置配置"""
    data = request.json
    for key, value in data.items():
        Config.set(key, value)
    return jsonify({'status': 'ok'})


@api_bp.route('/config/llm/test', methods=['POST'])
def test_llm():
    """测试 LLM 连接"""
    data = request.json
    provider = data.get('provider', 'deepseek')
    api_key = data.get('api_key')
    
    try:
        client = LLMClient(provider=provider, api_key=api_key)
        result = client.chat([
            {"role": "user", "content": "Say 'OK' if you can understand me."}
        ])
        return jsonify({'status': 'ok', 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


# ===== 搜索 API =====

@api_bp.route('/search/parse', methods=['POST'])
def parse_product():
    """解析商品描述，生成搜索关键词"""
    data = request.json
    description = data.get('description', '')
    
    try:
        result = parse_product_description(description)
        return jsonify({'status': 'ok', 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@api_bp.route('/search/run', methods=['POST'])
def run_search():
    """Execute search task."""
    data = request.json or {}
    queries = data.get('queries', [])
    product_desc = data.get('product_desc', '')
    auto_import = data.get('auto_import', True)
    icp = data.get('icp') if isinstance(data.get('icp'), dict) else None

    if not queries:
        return jsonify({'status': 'error', 'message': 'No queries provided'}), 400

    task = SearchTask(
        keyword=', '.join([q.get('query', '') for q in queries if isinstance(q, dict)]),
        product_desc=product_desc,
        status='running'
    )
    db.session.add(task)
    db.session.commit()

    try:
        searcher = Searcher()
        llm_client = _build_scoring_client()

        if not icp:
            try:
                icp = parse_product_description(product_desc)
            except Exception:
                icp = {
                    'product_name': product_desc,
                    'target_market': '',
                    'target_role': [],
                }

        results = searcher.search_multi(queries)
        scored_results = []
        imported_count = 0

        for r in results:
            lead_for_score = {
                'name': r.get('name', ''),
                'company': r.get('company', '') or r.get('username', ''),
                'bio': r.get('bio', ''),
                'platform': r.get('platform', ''),
                'email': r.get('email', ''),
                'url': r.get('url', ''),
            }
            score_result = _score_lead_with_fallback(lead_for_score, icp, llm_client=llm_client)

            merged = dict(r)
            merged['score'] = _clamp_score(score_result.get('score'))
            merged['is_target'] = score_result.get('is_target')
            merged['score_reason'] = score_result.get('reason', '')
            merged['score_tags'] = score_result.get('tags', []) or []
            scored_results.append(merged)

            if auto_import:
                lead_tags = [str(r.get('type', '')).strip()]
                lead_tags.extend([str(tag).strip() for tag in merged['score_tags']])
                lead_tags = [tag for tag in lead_tags if tag]

                lead = Lead(
                    name=r.get('name', ''),
                    company=r.get('company', '') or r.get('username', ''),
                    email=r.get('email', ''),
                    url=r.get('url', ''),
                    platform=r.get('platform', ''),
                    notes=r.get('bio', ''),
                    tags=','.join(lead_tags),
                    score=merged['score'],
                    is_target=merged['is_target']
                )
                db.session.add(lead)
                imported_count += 1

        if auto_import and scored_results:
            db.session.commit()

        task.status = 'completed'
        task.total_results = len(scored_results)
        task.found_results = imported_count
        task.completed_at = db.func.now()
        db.session.commit()

        safe_results = []
        for r in scored_results:
            safe_results.append({
                'name': str(r.get('name', ''))[:100],
                'username': str(r.get('username', ''))[:50],
                'company': str(r.get('company', ''))[:160],
                'email': str(r.get('email', ''))[:200],
                'url': str(r.get('url', ''))[:500],
                'bio': str(r.get('bio', ''))[:500],
                'platform': str(r.get('platform', '')),
                'type': str(r.get('type', '')),
                'score': _clamp_score(r.get('score')),
                'is_target': r.get('is_target'),
                'score_tags': r.get('score_tags', []),
            })

        return jsonify({
            'status': 'ok',
            'task_id': task.id,
            'results': safe_results,
            'imported': imported_count,
            'queries_total': len(queries),
        })

    except Exception as e:
        task.status = 'failed'
        db.session.commit()
        return jsonify({'status': 'error', 'message': str(e)}), 400


@api_bp.route('/leads', methods=['GET'])
def get_leads():
    """获取客户列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    platform = request.args.get('platform')
    is_target = request.args.get('is_target')
    search = request.args.get('search')
    
    query = Lead.query
    
    if platform:
        query = query.filter(Lead.platform == platform)
    if is_target:
        query = query.filter(Lead.is_target == (is_target == 'true'))
    if search:
        query = query.filter(
            db.or_(
                Lead.name.ilike(f'%{search}%'),
                Lead.company.ilike(f'%{search}%'),
                Lead.email.ilike(f'%{search}%')
            )
        )
    
    pagination = query.order_by(Lead.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'items': [l.to_dict() for l in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page
    })


@api_bp.route('/leads/<int:lead_id>', methods=['GET'])
def get_lead(lead_id):
    """获取单个客户"""
    lead = Lead.query.get_or_404(lead_id)
    return jsonify(lead.to_dict())


@api_bp.route('/leads', methods=['POST'])
def create_lead():
    """创建客户"""
    data = request.json
    lead = Lead(
        name=data.get('name'),
        company=data.get('company'),
        job_title=data.get('job_title'),
        email=data.get('email'),
        phone=data.get('phone'),
        wechat=data.get('wechat'),
        whatsapp=data.get('whatsapp'),
        url=data.get('url'),
        platform=data.get('platform'),
        tags=data.get('tags'),
        notes=data.get('notes'),
        score=data.get('score', 0),
        is_target=data.get('is_target')
    )
    db.session.add(lead)
    db.session.commit()
    return jsonify(lead.to_dict())


@api_bp.route('/leads/<int:lead_id>', methods=['PUT'])
def update_lead(lead_id):
    """更新客户"""
    lead = Lead.query.get_or_404(lead_id)
    data = request.json
    
    for key in ['name', 'company', 'job_title', 'email', 'phone', 'wechat', 
                'whatsapp', 'url', 'platform', 'tags', 'notes', 'score', 'is_target']:
        if key in data:
            setattr(lead, key, data[key])
    
    db.session.commit()
    return jsonify(lead.to_dict())


@api_bp.route('/leads/<int:lead_id>', methods=['DELETE'])
def delete_lead(lead_id):
    """删除客户"""
    lead = Lead.query.get_or_404(lead_id)
    db.session.delete(lead)
    db.session.commit()
    return jsonify({'status': 'ok'})


@api_bp.route('/leads/import', methods=['POST'])
def import_leads():
    """批量导入客户"""
    data = request.json
    leads_data = data.get('leads', [])
    icp = data.get('icp', {})
    
    imported = 0
    for ld in leads_data:
        # 使用 LLM 评估
        if icp:
            try:
                score_result = score_lead(ld, icp)
                ld['score'] = score_result.get('score', 50)
                ld['is_target'] = score_result.get('is_target')
                ld['tags'] = ','.join(score_result.get('tags', []))
            except:
                pass
        
        lead = Lead(**ld)
        db.session.add(lead)
        imported += 1
    
    db.session.commit()
    return jsonify({'status': 'ok', 'imported': imported})


@api_bp.route('/leads/export', methods=['GET'])
def export_leads():
    """导出客户为 Excel"""
    import pandas as pd
    
    leads = Lead.query.all()
    data = [l.to_dict() for l in leads]
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Leads')
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'leads_{pd.Timestamp.now().strftime("%Y%m%d")}.xlsx'
    )


# ===== 任务 API =====

@api_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """获取搜索任务列表"""
    tasks = SearchTask.query.order_by(SearchTask.created_at.desc()).limit(50).all()
    return jsonify([t.to_dict() for t in tasks])


@api_bp.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """获取单个任务"""
    task = SearchTask.query.get_or_404(task_id)
    return jsonify(task.to_dict())


# ===== 仪表盘 API =====

@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """获取仪表盘数据"""
    total = Lead.query.count()
    by_platform = db.session.query(
        Lead.platform, db.func.count(Lead.id)
    ).group_by(Lead.platform).all()
    
    target_count = Lead.query.filter(Lead.is_target == True).count()
    
    recent = Lead.query.order_by(Lead.created_at.desc()).limit(10).all()
    
    return jsonify({
        'total_leads': total,
        'target_leads': target_count,
        'by_platform': {p: c for p, c in by_platform},
        'recent_leads': [l.to_dict() for l in recent]
    })
