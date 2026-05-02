import pdfkit
import imgkit
from flask import render_template_string
import uuid
import io

LIGHT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { 
            font-family: 'Inter', sans-serif; 
            color: #334155; 
            background: #ffffff; 
            padding: 40px; 
            margin: 0;
            line-height: 1.6;
        }
        .header { 
            text-align: center; 
            border-bottom: 3px solid #d4af37; 
            padding-bottom: 25px; 
            margin-bottom: 30px; 
        }
        .logo-text { 
            font-size: 42px; 
            font-weight: 900; 
            color: #d4af37; 
            margin-bottom: 10px; 
            letter-spacing: 2px;
            text-shadow: 0px 2px 4px rgba(0,0,0,0.1);
        }
        .logo-subtext {
            font-size: 14px; 
            font-weight: 600; 
            color: #94a3b8; 
            margin-top: -5px; 
            margin-bottom: 15px; 
            letter-spacing: 1px;
        }
        .title { 
            color: #1e293b; 
            font-size: 32px; 
            font-weight: 800; 
            margin: 0; 
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .subtitle {
            color: #64748b;
            font-size: 16px;
            margin-top: 5px;
        }
        .score { 
            font-size: 24px; 
            color: #d4af37; 
            font-weight: 700;
            margin-top: 15px; 
        }
        
        .q-block { 
            background: #f8fafc; 
            padding: 24px; 
            border-radius: 12px; 
            margin-bottom: 24px;
            page-break-inside: avoid; 
            border-left: 5px solid #d4af37;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05);
        }
        .q-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 8px;
        }
        .q-number {
            font-size: 14px;
            font-weight: 700;
            color: #64748b;
            letter-spacing: 1px;
        }
        .q-status {
            font-size: 14px;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 4px;
            float: right;
        }
        .q-status.correct {
            color: #15803d;
            background: #dcfce7;
        }
        .q-status.wrong {
            color: #b91c1c;
            background: #fee2e2;
        }
        
        .q-text { 
            font-weight: 700; 
            font-size: 18px; 
            margin-bottom: 16px; 
            color: #0f172a;
        }
        .options {
            display: block;
            margin-bottom: 16px;
        }
        .opt {
            padding: 10px 14px;
            border-radius: 8px;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            font-size: 15px;
            margin-bottom: 8px;
        }
        .opt.correct {
            background: #dcfce7;
            border-color: #22c55e;
            color: #166534;
            font-weight: 600;
        }
        .opt.wrong {
            background: #fee2e2;
            border-color: #ef4444;
            color: #991b1b;
            font-weight: 600;
            text-decoration: line-through;
        }
        .insight {
            background: #eff6ff;
            padding: 12px;
            border-radius: 8px;
            border-left: 3px solid #3b82f6;
            margin-top: 12px;
        }
        .insight-label {
            font-size: 12px;
            font-weight: 700;
            color: #2563eb;
            margin-bottom: 4px;
            letter-spacing: 1px;
        }
        .insight-text {
            font-size: 14px;
            color: #1e3a8a;
            margin: 0;
        }
        
        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #94a3b8;
            border-top: 1px solid #e2e8f0;
            padding-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo-text">𝔸β𝕐</div>
        <div class="logo-subtext">𝔸int βeta 𝕐et</div>
        <div class="title">Sacred Review</div>
        <div class="subtitle">{{ topic_name }}</div>
        <div class="score">Final Score: {{ score }}</div>
    </div>
    
    {% for idx in range(questions|length) %}
        {% set q = questions[idx] %}
        {% set ans = user_answers[idx] %}
        <div class="q-block">
            <div class="q-header">
                <span class="q-number">QUESTION {{ idx + 1 }}</span>
                {% if ans.isCorrect %}
                    <span class="q-status correct">VERIFIED</span>
                {% else %}
                    <span class="q-status wrong">FAILED</span>
                {% endif %}
                <div style="clear: both;"></div>
            </div>
            
            <div class="q-text">{{ q.question }}</div>
            
            <div class="options">
                {% for opt in q.options %}
                    {% set is_correct_opt = (opt == q.correct) %}
                    {% set is_selected_wrong = (opt == ans.selected and not ans.isCorrect) %}
                    
                    <div class="opt {% if is_correct_opt %}correct{% elif is_selected_wrong %}wrong{% endif %}">
                        {{ opt }}
                    </div>
                {% endfor %}
            </div>
            
            <div class="insight">
                <div class="insight-label">INSIGHT</div>
                <p class="insight-text">{{ q.explanation }}</p>
            </div>
        </div>
    {% endfor %}
    
    <div class="footer">
        Generated by 𝔸β𝕐 • The Scriptorium
    </div>
</body>
</html>
"""

def generate_filename(config, fmt="pdf"):
    quiz_type = config.get('type', 'General').capitalize()
    specifics = config.get('value', '')
    if isinstance(specifics, str):
        specifics = specifics.replace(" ", "_").replace("/", "-")
    elif isinstance(specifics, list):
        specifics = "_".join(str(s) for s in specifics).replace(" ", "_")
        
    random_hash = uuid.uuid4().hex[:4]
    
    if specifics:
        return f"Sacred_Review_{quiz_type}_{specifics}_{random_hash}.{fmt}"
    return f"Sacred_Review_{quiz_type}_{random_hash}.{fmt}"

def generate_export_file(score, questions, user_answers, config, format_type="pdf"):
    topic_name = f"{config.get('type', 'General').capitalize()}: {config.get('value', 'Assorted')}"
    
    html = render_template_string(
        LIGHT_TEMPLATE,
        score=score,
        topic_name=topic_name,
        questions=questions,
        user_answers=user_answers
    )
    
    if format_type == "png":
        options = {
            'format': 'png',
            'width': 800,
            'encoding': "UTF-8"
        }
        return imgkit.from_string(html, False, options=options)
    else:
        options = {
            'page-size': 'Letter',
            'margin-top': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'margin-right': '0.75in',
            'encoding': "UTF-8"
        }
        return pdfkit.from_string(html, False, options=options)
