import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  final String sessionUuid;
  final String userUuid;

  ApiService() 
      : sessionUuid = const Uuid().v4(),
        userUuid = const Uuid().v4();

  Future<String> _getBackendUrl() async {
    final prefs = await SharedPreferences.getInstance();
    // Default to the IP we found earlier, but it can be changed in settings
    String ip = prefs.getString('backend_ip') ?? "192.168.1.6";
    return "http://$ip:5000/collect";
  }

  Future<bool> sendData(String audioFilePath, double lat, double lon, double alt) async {
    try {
      final int timestampMs = DateTime.now().millisecondsSinceEpoch;
      final String backendUrl = await _getBackendUrl();

      var request = http.MultipartRequest('POST', Uri.parse(backendUrl));
      
      // Add JSON Metadata
      request.fields['metadata'] = jsonEncode({
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "session_uuid": sessionUuid,
        "user_uuid": userUuid,
        "type": "new",
        "source": "gnss",
        "test": false,
        "time": timestampMs
      });

      // Add Audio File
      request.files.add(
        await http.MultipartFile.fromPath(
          'audio',
          audioFilePath,
        )
      );

      // Send
      var response = await request.send().timeout(const Duration(seconds: 15));
      
      if (response.statusCode == 200) {
        print("Successfully uploaded noise sample to backend! lat=$lat lon=$lon");
        return true;
      } else {
        final body = await response.stream.bytesToString();
        print("Failed to upload. Status code: ${response.statusCode}, Body: $body");
        return false;
      }
    } catch (e) {
      print("Network Error: $e");
      return false;
    }
  }
}
