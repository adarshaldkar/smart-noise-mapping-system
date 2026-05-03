import 'dart:convert';
import 'dart:io';
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

  /// Sends data directly to the server. If it fails, saves to offline queue.
  /// Returns "success", "queued", or "error".
  Future<String> sendData(String audioFilePath, double lat, double lon, double alt) async {
    final int timestampMs = DateTime.now().millisecondsSinceEpoch;
    
    // Attempt upload
    bool success = await _uploadSample(audioFilePath, lat, lon, alt, timestampMs);
    
    if (success) {
      return "success";
    } else {
      // Failed to upload, save to offline queue
      await _queueOfflineSample(audioFilePath, lat, lon, alt, timestampMs);
      return "queued";
    }
  }

  /// Inner method to perform the actual HTTP request
  Future<bool> _uploadSample(String audioFilePath, double lat, double lon, double alt, int timestampMs) async {
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
        print("Successfully uploaded noise sample! lat=$lat lon=$lon");
        return true;
      } else {
        print("Failed to upload. Status code: ${response.statusCode}");
        return false;
      }
    } catch (e) {
      print("Network Error during upload: $e");
      return false;
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

        bool success = await _uploadSample(
          path, 
          item['lat'], 
          item['lon'], 
          item['alt'], 
          item['timestamp']
        );

        if (success) {
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
