import os
import pytest

from app.ai.services.ai_service import AIService
from app.ai.services.alfred_ai import AlfredAiService


class DummyResp:
    def __init__(self, response_text):
        self._response_text = response_text

    def json(self):
        return {"response": self._response_text}


def test_parse_intent_rule_based_no_llm(monkeypatch):
    service = AIService(model_loader=None)
    intent = service.parse_intent('bật đèn phòng ngủ')
    assert intent['intent'] == 'control'
    assert intent['action'] == 'on'


def test_parse_intent_rule_based_english_room_and_type(monkeypatch):
    service = AIService(model_loader=None)
    intent = service.parse_intent('turn on fan in kitchen')
    assert intent['intent'] == 'control'
    assert intent['action'] == 'on'
    assert intent['device_type'] == 'fan'
    assert intent['room'] == 'KITCHEN'


def test_parse_intent_rule_based_vietnamese_unaccented_fan_room(monkeypatch):
    service = AIService(model_loader=None)
    intent = service.parse_intent('bat quat phong kitchen')
    assert intent['intent'] == 'control'
    assert intent['action'] == 'on'
    assert intent['device_type'] == 'fan'
    assert intent['room'] == 'KITCHEN'


def test_parse_intent_llm_json_basic(monkeypatch):
    service = AIService(model_loader=None)

    def fake_post(url, json, timeout):
        assert 'api/generate' in url
        return DummyResp('{"intent":"chat","action":null,"device_type":null,"room":null,"floor":null,"reply":null}')

    monkeypatch.setattr('requests.post', fake_post)

    intent = service.parse_intent('tôi cần giúp đỡ')
    assert intent['intent'] == 'chat'


def test_parse_intent_llm_malformed_json_extra_data(monkeypatch):
    service = AIService(model_loader=None)

    def fake_post(url, json, timeout):
        return DummyResp('{"intent":"chat","action":null} extra data')

    monkeypatch.setattr('requests.post', fake_post)

    intent = service.parse_intent('random question')
    assert intent['intent'] == 'chat'


def test_alfred_ai_gemini_key_guard(monkeypatch):
    # Ensure GEMINI_API_KEY not set
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    alfred = AlfredAiService()

    reply = alfred.ask_alfred('hello', 'context')
    assert 'GEMINI_API_KEY' in reply
