Map<String, String> apiJsonHeaders([Map<String, String>? extra]) {
  return <String, String>{
    'Content-Type': 'application/json',
    ...?extra,
  };
}
