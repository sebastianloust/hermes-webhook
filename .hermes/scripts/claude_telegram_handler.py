#!/usr/bin/env python3
"""
Gemini Telegram Handler — Intelligent conversation with memory
Integrates google-generativeai SDK for real-time responses
Uses conversation history for context-aware replies
"""

import json
import os
from datetime import datetime
from typing import List, Dict

from claude_api_client import get_gemini_model, GeminiClientError


# Configuration
TRACKER_PATH = os.getenv('PRIORITY_TRACKER_PATH', os.path.expanduser('~/.hermes/priority_tracker.json'))
CONVERSATION_LOG_PATH = os.getenv('CONVERSATION_LOG_PATH', os.path.expanduser('~/.hermes/conversation_log.json'))
MAX_CONVERSATION_HISTORY = 50


def load_json(path: str) -> dict:
    """Load JSON file safely"""
    try:
        if not os.path.exists(path):
            return {}
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return {}


def save_json(path: str, data: dict) -> bool:
    """Save JSON file safely with directory creation"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {path}: {e}")
        return False


def build_system_prompt(tracker: dict) -> str:
    """Build system prompt with Ruben's context from priority tracker"""
    urgent_tasks = tracker.get('urgente_7days', [])
    financial = tracker.get('financial_snapshot', {})
    config = tracker.get('hermes_config', {})

    # Task list context
    urgent_text = ""
    if urgent_tasks:
        urgent_text = "\n\nTareas urgentes (próximos 7 días):\n"
        for task in urgent_tasks[:5]:
            days = task.get('days_remaining', '?')
            urgent_text += f"- {task.get('title', 'Sin título')} ({days} días)\n"

    # Financial context
    financial_text = ""
    if financial:
        balances = financial.get('balance', {})
        financial_text = f"\n\nEstado financiero:\n"
        financial_text += f"- Checking (USAA): ${balances.get('checking', 0):.2f}\n"
        financial_text += f"- Savings: ${balances.get('savings', 0):.2f}\n"

    # Schedule context
    schedule_text = ""
    if config:
        schedule_text = f"\n\nHorario de Hermes:\n"
        schedule_text += f"- Morning briefing: {config.get('briefing_time', '6:00 AM')}\n"
        schedule_text += f"- Evening check-in: {config.get('checkin_time', '5:00 PM')}\n"

    prompt = f"""Eres Hermes, el asistente personal inteligente de Ruben. Hablas en español, eres directo y práctico.

Tu rol:
- Responder preguntas sobre las prioridades, finanzas, educación y proyectos de Ruben
- Entender el contexto de su vida y sus deadlines
- Ser conciso pero útil
- Sugerir acciones cuando sea relevante

CONTEXTO ACTUAL DE RUBEN:
{urgent_text}{financial_text}{schedule_text}

Responde en español, de manera natural y conversacional. Si no sabes algo específico, pregunta o sugiere cómo obtener la información."""

    return prompt


def load_conversation_history(max_messages: int = 10) -> List[Dict]:
    """
    Load conversation history and convert to Gemini format.
    Gemini uses {"role": "user"|"model", "parts": [{"text": "..."}]}
    """
    log = load_json(CONVERSATION_LOG_PATH)
    messages = log.get('messages', [])

    # Get last N messages
    recent = messages[-max_messages:] if len(messages) > max_messages else messages

    # Convert to Gemini format
    history = []
    for msg in recent:
        # User message
        if msg.get('user'):
            history.append({
                "role": "user",
                "parts": [{"text": msg['user']}]
            })
        # Assistant message
        if msg.get('agent'):
            history.append({
                "role": "model",
                "parts": [{"text": msg['agent']}]
            })

    return history


def call_gemini_with_context(user_message: str, conversation_history: List[Dict]) -> str:
    """
    Call Gemini with conversation history and context.
    Returns the model's response or error message.
    """
    try:
        model = get_gemini_model()
        tracker = load_json(TRACKER_PATH)
        system_prompt = build_system_prompt(tracker)

        # Start chat with history and system prompt
        full_history = conversation_history.copy()
        # Prepend system instruction as first user message if no history
        if not full_history:
            full_history.append({
                "role": "user",
                "parts": [{"text": system_prompt + "\n\n" + user_message}]
            })
        else:
            # Add system context to the new message
            full_history.append({
                "role": "user",
                "parts": [{"text": system_prompt + "\n\n[Nuevo mensaje de usuario]: " + user_message}]
            })

        chat = model.start_chat(history=conversation_history)
        response = chat.send_message(system_prompt + "\n\n" + user_message)
        return response.text

    except GeminiClientError as e:
        error_msg = f"⚠️ Error de configuración: {str(e)}"
        print(f"Gemini client error: {e}")
        return error_msg
    except Exception as e:
        error_msg = f"⚠️ Error al procesar tu mensaje. Intenta de nuevo."
        print(f"Error calling Gemini: {e}")
        return error_msg


def save_conversation(user_msg: str, ai_response: str) -> bool:
    """Save conversation with rolling 50-message window"""
    try:
        log = load_json(CONVERSATION_LOG_PATH)

        if not isinstance(log, dict):
            log = {}
        if 'messages' not in log:
            log['messages'] = []

        # Add both user and AI messages
        log['messages'].append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg,
            "agent": ai_response,
            "context_snapshot": load_json(TRACKER_PATH)
        })

        # Keep only last 50 messages
        if len(log['messages']) > MAX_CONVERSATION_HISTORY:
            log['messages'] = log['messages'][-MAX_CONVERSATION_HISTORY:]

        log['last_updated'] = datetime.now().isoformat()
        return save_json(CONVERSATION_LOG_PATH, log)

    except Exception as e:
        print(f"Error saving conversation: {e}")
        return False


def get_conversation_summary(num_messages: int = 5) -> str:
    """Get recent conversation summary for context"""
    try:
        log = load_json(CONVERSATION_LOG_PATH)
        messages = log.get('messages', [])
        recent = messages[-num_messages:] if len(messages) > num_messages else messages

        summary = "Últimos mensajes:\n"
        for msg in recent:
            timestamp = msg.get('timestamp', 'unknown')[:16]
            user_text = msg.get('user', '')[:100]
            summary += f"[{timestamp}] Usuario: {user_text}...\n"

        return summary

    except Exception as e:
        print(f"Error getting conversation summary: {e}")
        return "No se pudo cargar historial."
