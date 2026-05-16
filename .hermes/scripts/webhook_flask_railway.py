#!/usr/bin/env python3
"""
Hermes Webhook Server for Railway
Real-time Telegram webhook handler with intelligent agent processing
"""

import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import re
from claude_telegram_handler import call_gemini_with_context, load_conversation_history, save_conversation

# Load environment variables
# Try multiple paths for development and production
env_paths = [
    '/app/.env',  # Docker container path
    os.path.expanduser('~/.hermes/.env'),  # Local development
    '.env'  # Current directory fallback
]
for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

app = Flask(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
VAULT_PATH = os.getenv('VAULT_PATH')
TRACKER_PATH = os.getenv('PRIORITY_TRACKER_PATH')
DAILY_LOG = os.path.join(VAULT_PATH, 'DAILY_LOG.md') if VAULT_PATH else None
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'dev-secret')

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment")


def load_json(path):
    """Load JSON file safely"""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_json(path, data):
    """Save JSON file safely"""
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except:
        return False


def send_telegram(message, chat_id=None):
    """Send message to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id or TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        app.logger.error(f"Telegram error: {e}")
        return False


def log_to_daily(message):
    """Append to DAILY_LOG.md"""
    if not DAILY_LOG:
        return False
    try:
        with open(DAILY_LOG, 'a') as f:
            f.write(f"\n### {datetime.now().strftime('%H:%M')} - Webhook\n")
            f.write(f"{message}\n")
        return True
    except:
        return False


def parse_event(message):
    """Extract event details from natural language"""
    event = {
        "title": "",
        "date": None,
        "time": None,
        "location": ""
    }

    # Extract title (first 5-7 words)
    words = message.split()
    event['title'] = ' '.join(words[:7])

    # Try to find date patterns
    date_patterns = [
        (r'(\d{1,2}[/-]\d{1,2})', 'dd/mm'),
        (r'(mañana|tomorrow)', 'tomorrow'),
        (r'(hoy|today)', 'today'),
        (r'(próximo|next)', 'next'),
    ]

    for pattern, label in date_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            event['date'] = label
            break

    # Try to find time
    time_pattern = r'(\d{1,2}:\d{2}|\d{1}(?:am|pm))'
    time_match = re.search(time_pattern, message, re.IGNORECASE)
    if time_match:
        event['time'] = time_match.group(1)

    # Try to find location
    location_pattern = r'(?:en|at|lugar)\s+([A-Za-záéíóúñ\s]+)'
    location_match = re.search(location_pattern, message, re.IGNORECASE)
    if location_match:
        event['location'] = location_match.group(1).strip()

    return event


def analyze_intent(message):
    """Determine user intent from message"""
    msg_lower = message.lower()

    intents = {
        'task_completion': ['completar', 'hecho', 'listo', 'terminé', 'acabé', 'done'],
        'event_creation': ['evento', 'reunión', 'cita', 'meeting'],
        'email': ['envía', 'email', 'mail', 'escribir'],
        'financial': ['dinero', 'plata', 'presupuesto', 'financial', 'carro'],
        'education': ['escuela', 'tarea', 'examen', 'estudio', 'epcc'],
        'music': ['música', 'single', 'fer', 'label'],
        'help': ['ayuda', 'qué puedes', 'help', 'capaz']
    }

    for intent, keywords in intents.items():
        if any(kw in msg_lower for kw in keywords):
            return intent

    return 'general'


def handle_task_completion(message, tracker):
    """Handle task completion"""
    urgentes = tracker.get('urgente_7days', [])

    if not urgentes:
        return "✓ No hay tareas urgentes registradas. ¿Qué completaste?"

    response = "✓ ¿Cuál tarea completaste?\n\n"
    for i, task in enumerate(urgentes[:3], 1):
        days = task.get('days_remaining', '?')
        response += f"{i}. {task['title']} ({days} días)\n"

    response += "\nResponde con el número o el nombre de la tarea."
    return response


def handle_event_creation(message):
    """Handle event creation"""
    event = parse_event(message)

    response = f"📅 **Evento detectado:** {event['title']}\n\n"
    response += f"*Detalles extraídos:*\n"
    response += f"• **Fecha:** {event['date'] or 'No especificada'}\n"
    response += f"• **Hora:** {event['time'] or 'No especificada'}\n"
    response += f"• **Lugar:** {event['location'] or 'No especificado'}\n\n"
    response += "¿Confirmas estos detalles? Responde **sí** o proporciona correcciones."

    return response


def handle_financial_inquiry(message):
    """Handle financial questions (auto-response)"""
    response = "💰 **Estado Financiero:**\n\n"
    response += "• **Financial Aid EPCC:** $2,000 (vence 2026-05-30)\n"
    response += "• **Abogado:** $1,500-1,800 (~1 mes)\n"
    response += "• **GeoFinance:** Pausado\n\n"
    response += "¿Necesitas más detalles?"

    return response


def handle_education(message):
    """Handle education inquiries"""
    response = "📚 **Estado de Cursos:**\n\n"
    response += "• **INRW 0311:** En progreso\n"
    response += "• **ENGL 1301:** En progreso\n"
    response += "• **CLEP/TSIA2:** 75% completado\n\n"
    response += "¿Necesitas ayuda con algo específico?"

    return response


def handle_message(user_message, tracker):
    """Main message handler with intelligent routing"""
    intent = analyze_intent(user_message)

    if intent == 'task_completion':
        return handle_task_completion(user_message, tracker)
    elif intent == 'event_creation':
        return handle_event_creation(user_message)
    elif intent == 'financial':
        return handle_financial_inquiry(user_message)
    elif intent == 'education':
        return handle_education(user_message)
    elif intent == 'help':
        response = "🤖 **Soy tu asistente Hermes. Puedo:**\n\n"
        response += "✓ Registrar eventos en tu calendar\n"
        response += "✓ Marcar tareas como completadas\n"
        response += "✓ Darte estado financiero/educativo\n"
        response += "✓ Redactar emails\n"
        response += "✓ Ayudarte con prioridades\n\n"
        response += "¿Qué necesitas?"
        return response
    else:
        return f"Entendido: **{user_message}**\n\n¿Hay algo que deba hacer o actualizar?"


@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """Handle Telegram webhook"""
    try:
        update = request.get_json()

        if not update or 'message' not in update:
            return jsonify({'ok': True}), 200

        message = update['message']
        user_message = message.get('text', '')
        user_id = message.get('from', {}).get('id')

        if not user_message:
            return jsonify({'ok': True}), 200

        # Process message with Gemini API (with conversation memory)
        conversation_history = load_conversation_history(max_messages=10)
        response = call_gemini_with_context(user_message, conversation_history)
        save_conversation(user_message, response)

        # Send response back to Telegram
        send_telegram(response)

        # Log to daily
        log_to_daily(f"**User:** {user_message}\n\n**Agent:** {response}")

        return jsonify({'ok': True}), 200

    except Exception as e:
        app.logger.error(f"Webhook error: {e}")
        send_telegram("⚠️ Error interno. Intenta de nuevo.")
        return jsonify({'ok': True}), 200


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'telegram_configured': bool(TELEGRAM_BOT_TOKEN)
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'name': 'Hermes Webhook',
        'version': '1.0',
        'status': 'running',
        'endpoints': {
            'webhook': '/webhook/telegram',
            'health': '/health'
        }
    }), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
