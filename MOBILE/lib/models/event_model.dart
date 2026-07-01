
enum EventType { medicine, activity, appointment, note }

EventType eventTypeFromString(String? s) {
  switch (s) {
    case 'medicine': return EventType.medicine;
    case 'activity': return EventType.activity;
    case 'appointment': return EventType.appointment;
    case 'note': return EventType.note;
    default: return EventType.medicine;
  }
}

String eventTypeToString(EventType t) {
  switch (t) {
    case EventType.medicine: return 'medicine';
    case EventType.activity: return 'activity';
    case EventType.appointment: return 'appointment';
    case EventType.note: return 'note';
  }
}

class EventModel {
  final int? id; // null for local events
  final EventType type;
  final String title;
  final String? dose; // only for medicine
  final String time; // HH:MM
  final String days; // recurrence pattern
  final String? notes;
  final bool takenToday; // only for medicine

  EventModel({
    this.id,
    required this.type,
    required this.title,
    this.dose,
    required this.time,
    required this.days,
    this.notes,
    this.takenToday = false,
  });

  factory EventModel.fromJson(Map<String, dynamic> json) {
    return EventModel(
      id: json['id'] as int?,
      type: eventTypeFromString(json['type'] as String?),
      title: json['title'] ?? json['name'] ?? '',
      dose: json['dose'],
      time: json['time'] ?? '',
      days: json['days'] ?? 'daily',
      notes: json['notes'],
      takenToday: json['taken_today'] == true,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'type': eventTypeToString(type),
    'title': title,
    if (dose != null) 'dose': dose,
    'time': time,
    'days': days,
    if (notes != null) 'notes': notes,
    'taken_today': takenToday,
  };
}
