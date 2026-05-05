import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with SingleTickerProviderStateMixin {
  bool _isRecording = false;
  Position? _currentPosition;
  late AnimationController _pulseController;
  final AudioRecorder _audioRecorder = AudioRecorder();
  final ApiService _apiService = ApiService();
  
  int _samplesSent = 0;
  int _samplesQueued = 0;
  Timer? _recordingTimer;
  StreamSubscription<Amplitude>? _amplitudeSub;
  double _currentDb = -60.0;
  
  String _uploadState = "READY"; // READY, RECORDING, UPLOADING, SUCCESS, ERROR
  Color _stateColor = Colors.greenAccent;
  
  final TextEditingController _nameController = TextEditingController();
  String _userName = "Anonymous";

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    
    _loadUserName();
    _requestPermissions();
    _updateQueueCount();
  }

  Future<void> _loadUserName() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _userName = prefs.getString('user_name') ?? "Anonymous";
      _nameController.text = _userName == "Anonymous" ? "" : _userName;
    });
    _apiService.setUserName(_userName);
  }

  Future<void> _saveUserName(String name) async {
    final prefs = await SharedPreferences.getInstance();
    String finalName = name.trim().isEmpty ? "Anonymous" : name.trim();
    await prefs.setString('user_name', finalName);
    setState(() {
      _userName = finalName;
    });
    _apiService.setUserName(finalName);
  }

  Future<void> _updateQueueCount() async {
    int count = await _apiService.getOfflineQueueCount();
    if (mounted) {
      setState(() {
        _samplesQueued = count;
      });
    }
  }

  Future<void> _requestPermissions() async {
    await [
      Permission.microphone,
      Permission.locationWhenInUse,
    ].request();
    
    _updateLocation();
  }

  Future<void> _updateLocation() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) return;

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) return;
    }

    Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high);
    
    if (mounted) {
      setState(() {
        _currentPosition = position;
      });
    }
  }

  void _toggleRecording() {
    if (_isRecording) {
      _stopMapping();
    } else {
      _startMapping();
    }
  }

  void _startMapping() async {
    // Try syncing any offline data first
    await _apiService.syncOfflineQueue();
    await _updateQueueCount();

    setState(() {
      _isRecording = true;
      _samplesSent = 0;
      _uploadState = "INITIALIZING";
      _stateColor = Colors.orangeAccent;
    });

    _recordAndSendCycle();
    _recordingTimer = Timer.periodic(const Duration(seconds: 15), (timer) {
      _recordAndSendCycle();
    });
  }

  void _stopMapping() async {
    _recordingTimer?.cancel();
    _amplitudeSub?.cancel();
    if (await _audioRecorder.isRecording()) {
      await _audioRecorder.stop();
    }
    setState(() {
      _isRecording = false;
      _uploadState = "READY";
      _stateColor = Colors.greenAccent;
      _currentDb = -60.0;
    });
    _updateQueueCount();
  }

  Future<void> _recordAndSendCycle() async {
    try {
      await _updateLocation();
      
      if (_currentPosition == null) return;

      final String tempPath = '${Directory.systemTemp.path}/noise_sample_${DateTime.now().millisecondsSinceEpoch}.m4a';
      
      if (await _audioRecorder.hasPermission()) {
        if (!mounted) return;
        setState(() {
          _uploadState = "RECORDING (5s)";
          _stateColor = Colors.redAccent;
        });

        await _audioRecorder.start(
          const RecordConfig(encoder: AudioEncoder.aacLc, sampleRate: 16000, numChannels: 1),
          path: tempPath,
        );

        _amplitudeSub?.cancel();
        _amplitudeSub = _audioRecorder.onAmplitudeChanged(const Duration(milliseconds: 50)).listen((amp) {
          if (mounted) {
            setState(() {
              // Current returns values usually from -160 to 0
              _currentDb = amp.current; 
            });
          }
        });

        await Future.delayed(const Duration(seconds: 5));
        
        final String? path = await _audioRecorder.stop();
        _amplitudeSub?.cancel();
        
        if (path != null && mounted) {
          setState(() {
            _uploadState = "UPLOADING";
            _stateColor = Colors.blueAccent;
          });

          String result = await _apiService.sendData(
            path, 
            _currentPosition!.latitude, 
            _currentPosition!.longitude, 
            _currentPosition!.altitude
          );

          if (mounted) {
            if (result == "success") {
              setState(() {
                _samplesSent++;
                _uploadState = "SUCCESS";
                _stateColor = Colors.greenAccent;
              });
            } else if (result == "queued") {
              setState(() {
                _uploadState = "QUEUED OFFLINE";
                _stateColor = Colors.orangeAccent;
              });
              _updateQueueCount();
            } else {
              setState(() {
                _uploadState = "ERROR";
                _stateColor = Colors.red;
              });
            }
          }
        }
      }
    } catch (e) {
      debugPrint("Error in recording cycle: $e");
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _recordingTimer?.cancel();
    _amplitudeSub?.cancel();
    _audioRecorder.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Calculate a 0-1 scale for the visualizer from the dB value (-60 to 0 typical)
    double meterValue = max(0, (_currentDb + 60) / 60);

    return Scaffold(
      backgroundColor: const Color(0xFF121212),
      resizeToAvoidBottomInset: false,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text('NOISE MAPPER', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 3, color: Colors.white)),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white70),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const SettingsScreen()),
              );
            },
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Name Input Field
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              child: TextField(
                controller: _nameController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: "Mapper's Name",
                  labelStyle: const TextStyle(color: Colors.white54),
                  hintText: "Enter your name for the map...",
                  hintStyle: const TextStyle(color: Colors.white24),
                  prefixIcon: const Icon(Icons.person, color: Colors.blueAccent),
                  filled: true,
                  fillColor: Colors.white.withOpacity(0.05),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(15),
                    borderSide: BorderSide.none,
                  ),
                ),
                onSubmitted: _saveUserName,
                onChanged: (val) {
                  if (!_isRecording) _saveUserName(val);
                },
              ),
            ),
            
            // Session Telemetry Bar
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              padding: const EdgeInsets.all(15),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.05),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white10),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _buildTelemetryItem(Icons.radar, "STATE", _uploadState, _stateColor),
                  _buildTelemetryItem(Icons.cloud_upload, "SENT", "$_samplesSent", Colors.blueAccent),
                  _buildTelemetryItem(Icons.sd_storage, "QUEUED", "$_samplesQueued", _samplesQueued > 0 ? Colors.orangeAccent : Colors.grey),
                ],
              ),
            ),
            
            const Spacer(),
            
            // Live dB Visualizer
            Stack(
              alignment: Alignment.center,
              children: [
                // Pulsing background rings based on dB level
                AnimatedBuilder(
                  animation: _pulseController,
                  builder: (context, child) {
                    return Container(
                      width: 280 + (meterValue * 50 * _pulseController.value),
                      height: 280 + (meterValue * 50 * _pulseController.value),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _stateColor.withOpacity(0.05 + (meterValue * 0.1)),
                        boxShadow: [
                          BoxShadow(
                            color: _stateColor.withOpacity(0.2 * meterValue),
                            blurRadius: 40,
                            spreadRadius: 20 * meterValue,
                          )
                        ],
                      ),
                    );
                  },
                ),
                // Inner Circle
                Container(
                  width: 200,
                  height: 200,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        Colors.black87,
                        Colors.black,
                      ],
                    ),
                    border: Border.all(
                      color: _stateColor.withOpacity(0.5),
                      width: 3,
                    ),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        _isRecording ? _currentDb.toStringAsFixed(1) : "--",
                        style: TextStyle(
                          fontSize: 48,
                          fontWeight: FontWeight.bold,
                          color: _isRecording ? Colors.white : Colors.white30,
                        ),
                      ),
                      Text(
                        'dB (RMS)',
                        style: TextStyle(
                          fontSize: 16,
                          color: Colors.white54,
                          letterSpacing: 2,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            
            const Spacer(),
            
            // Location Info Card (Glassmorphic)
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [Colors.white.withOpacity(0.1), Colors.white.withOpacity(0.05)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white.withOpacity(0.1)),
              ),
              child: Row(
                children: [
                  Icon(
                    _currentPosition != null ? Icons.gps_fixed : Icons.gps_not_fixed,
                    color: _currentPosition != null ? Colors.greenAccent : Colors.redAccent,
                    size: 32,
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('GPS STATUS', style: TextStyle(color: Colors.white54, fontSize: 12, letterSpacing: 1)),
                            Text(_apiService.sessionUuid.substring(0, 8).toUpperCase(), style: const TextStyle(color: Colors.white30, fontSize: 10)),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _currentPosition != null 
                              ? '${_currentPosition!.latitude.toStringAsFixed(4)}, ${_currentPosition!.longitude.toStringAsFixed(4)}'
                              : 'Acquiring Satellite...',
                          style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  )
                ],
              ),
            ),
            
            // Start Button
            Padding(
              padding: const EdgeInsets.only(bottom: 30.0, left: 20, right: 20),
              child: SizedBox(
                width: double.infinity,
                height: 65,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isRecording ? Colors.redAccent.withOpacity(0.8) : Colors.blueAccent.withOpacity(0.8),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                    elevation: 10,
                  ),
                  onPressed: _toggleRecording,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(_isRecording ? Icons.stop_rounded : Icons.play_arrow_rounded, size: 28),
                      const SizedBox(width: 10),
                      Text(
                        _isRecording ? 'STOP SESSION' : 'START MAPPING',
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, letterSpacing: 2),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTelemetryItem(IconData icon, String label, String value, Color color) {
    return Column(
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(height: 5),
        Text(value, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 2),
        Text(label, style: const TextStyle(color: Colors.white30, fontSize: 10, letterSpacing: 1)),
      ],
    );
  }
}
