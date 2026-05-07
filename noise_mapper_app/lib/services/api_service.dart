import 'dart:convert';
import 'dart:io';
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  final String sessionUuid;
  final String userUuid;
  String _userName = "Anonymous";

  ApiService() 
      : sessionUuid = const Uuid().v4(),
        userUuid = const Uuid().v4();

  void setUserName(String name) {
    _userName = name;
  }

  Future<String> _getBackendUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final savedIp = prefs.getString('backend_ip')?.trim();
    final fallbackHost = kIsWeb
        ? 'localhost'
        : (Platform.isAndroid ? '10.0.2.2' : 'localhost');
    String ip = (savedIp == null || savedIp.isEmpty) ? fallbackHost : savedIp;
    return "http://$ip:5000/collect";
  }

  /// Sends data directly to the server. If it fails, saves to offline queue.
  /// Returns "noise_class", "queued", or "error".
  Future<String> sendData(String audioFilePath, double lat, double lon, double alt) async {
    final int timestampMs = DateTime.now().millisecondsSinceEpoch;
    
    // Attempt upload
    String? result = await _uploadSample(audioFilePath, lat, lon, alt, timestampMs);
    
    if (result != null) {
      return result;
    } else {
      // Failed to upload, save to offline queue
      print("Upload failed or timed out. Saving to offline queue...");
      await _queueOfflineSample(audioFilePath, lat, lon, alt, timestampMs);
      return "queued";
    }
  }

  /// Inner method to perform the actual HTTP request
  /// Returns the detected noise class on success, or null on failure
  Future<String?> _uploadSample(String audioFilePath, double lat, double lon, double alt, int timestampMs) async {
    try {
      final String backendUrl = await _getBackendUrl();

      var request = http.MultipartRequest('POST', Uri.parse(backendUrl));
      
      // Add JSON Metadata
      request.fields['metadata'] = jsonEncode({
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "session_uuid": sessionUuid,
        "user_uuid": userUuid,
        "user_name": _userName,
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
      var response = await request.send().timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        final respStr = await response.stream.bytesToString();
        final data = jsonDecode(respStr);
        String noiseClass = data['noise_class'] ?? "Success";
        print("Successfully uploaded noise sample! Detected: $noiseClass");
        return noiseClass;
      } else {
        print("Failed to upload. Status code: ${response.statusCode}");
        return null;
      }
    } on SocketException catch (e) {
      print("Network Error: No Internet connection ($e)");
      return null;
    } on TimeoutException catch (e) {
      print("Network Error: Connection timed out ($e)");
      return null;
    } catch (e) {
      print("Network Error during upload: $e");
      return null;
    }
  }

  // --- OFFLINE QUEUE LOGIC ---

  Future<void> _queueOfflineSample(String path, double lat, double lon, double alt, int timestamp) async {
    final prefs = await SharedPreferences.getInstance();
    List<String> queue = prefs.getStringList('offline_queue') ?? [];
    
    // Save metadata as JSON string
    Map<String, dynamic> sample = {
      'path': path,
      'lat': lat,
      'lon': lon,
      'alt': alt,
      'timestamp': timestamp,
    };
    
    queue.add(jsonEncode(sample));
    await prefs.setStringList('offline_queue', queue);
    print("Sample queued offline. Total queued: ${queue.length}");
  }

  Future<int> getOfflineQueueCount() async {
    final prefs = await SharedPreferences.getInstance();
    List<String> queue = prefs.getStringList('offline_queue') ?? [];
    return queue.length;
  }

  /// Attempts to sync all queued items. Returns number of items successfully synced.
  Future<int> syncOfflineQueue() async {
    final prefs = await SharedPreferences.getInstance();
    List<String> queue = prefs.getStringList('offline_queue') ?? [];
    
    if (queue.isEmpty) return 0;

    int syncedCount = 0;
    List<String> remainingQueue = [];

    print("Attempting to sync ${queue.length} offline items...");

    for (String itemStr in queue) {
      try {
        Map<String, dynamic> item = jsonDecode(itemStr);
        String path = item['path'];
        
        // Verify file still exists before uploading
        if (!File(path).existsSync()) {
          print("Skipping queued item: audio file no longer exists at $path");
          continue; // Drop from queue
        }

        String? result = await _uploadSample(
          path, 
          item['lat'], 
          item['lon'], 
          item['alt'], 
          item['timestamp']
        );

        if (result != null) {
          syncedCount++;
          // Delete the temporary file now that it's uploaded
          try {
             File(path).deleteSync();
          } catch(e) {
            print("Could not delete temp file: $e");
          }
        } else {
          // Keep in queue
          remainingQueue.add(itemStr);
        }
      } catch (e) {
        print("Error processing offline item: $e");
        // Corrupted item, don't re-add
      }
    }

    // Save remaining items back
    await prefs.setStringList('offline_queue', remainingQueue);
    print("Synced $syncedCount items. Remaining in queue: ${remainingQueue.length}");
    
    return syncedCount;
  }
}
