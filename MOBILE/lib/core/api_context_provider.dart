import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';
import 'cfg_provider.dart';

final apiBaseUrlProvider = Provider<String>((ref) => ref.watch(cfgProvider));

final authHeadersProvider = Provider<Map<String, String>>(
  (ref) => ref.watch(authProvider).bearerHeader,
);