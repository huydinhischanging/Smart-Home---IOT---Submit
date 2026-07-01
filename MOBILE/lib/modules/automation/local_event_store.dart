import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../../models/event_model.dart';

class LocalEventStore {
  static const _key = 'local_events_v1';

  static Future<List<EventModel>> loadEvents() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return [];
    final list = jsonDecode(raw) as List;
    return list.map((e) => EventModel.fromJson(e)).toList();
  }

  static Future<void> saveEvents(List<EventModel> events) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = jsonEncode(events.map((e) => e.toJson()).toList());
    await prefs.setString(_key, raw);
  }

  static Future<void> addEvent(EventModel event) async {
    final events = await loadEvents();
    await saveEvents([...events, event]);
  }

  static Future<void> deleteEvent(int idx) async {
    final events = await loadEvents();
    if (idx < 0 || idx >= events.length) return;
    events.removeAt(idx);
    await saveEvents(events);
  }
}
