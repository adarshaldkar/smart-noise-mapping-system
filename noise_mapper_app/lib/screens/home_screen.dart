import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
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
  Timer? _recordingTimer;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    
    _requestPermissions();
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
    setState(() {
      _isRecording = true;
      _samplesSent = 0;
    });

    // Start the recording loop
    _recordAndSendCycle();
    _recordingTimer = Timer.periodic(const Duration(seconds: 15), (timer) {
      _recordAndSendCycle();
    });
  }

  void _stopMapping() async {
    _recordingTimer?.cancel();
    if (await _audioRecorder.isRecording()) {
      await _audioRecorder.stop();
    }
    setState(() {
      _isRecording = false;
    });
  }

  Future<void> _recordAndSendCycle() async {
    try {
      await _updateLocation();
      
      if (_currentPosition == null) return;

      // Start recording
      final String tempPath = '${Directory.systemTemp.path}/noise_sample.m4a';
      
      if (await _audioRecorder.hasPermission()) {
        await _audioRecorder.start(
          const RecordConfig(encoder: AudioEncoder.aacLc, sampleRate: 16000, numChannels: 1),
          path: tempPath,
        );

        // Record for exactly 5 seconds
        await Future.delayed(const Duration(seconds: 5));
        
        final String? path = await _audioRecorder.stop();
        
        if (path != null) {
          // Send to Backend
          bool success = await _apiService.sendData(
            path, 
            _currentPosition!.latitude, 
            _currentPosition!.longitude, 
            _currentPosition!.altitude
          );

          if (success && mounted) {
            setState(() {
              _samplesSent++;
            });
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
    _audioRecorder.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('NOISE MAPPER', style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2)),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
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
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Top Stats
            if (_isRecording)
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: Text(
                  'Samples Sent: $_samplesSent',
                  style: const TextStyle(color: Colors.white70, fontSize: 16),
                ),
              ),
              
            const Spacer(),
            
            // Central Meter
            GestureDetector(
              onTap: _toggleRecording,
              child: AnimatedBuilder(
                animation: _pulseController,
                builder: (context, child) {
                  return Container(
                    width: 250,
                    height: 250,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _isRecording ? Colors.red.withOpacity(0.1) : Colors.green.withOpacity(0.1),
                      boxShadow: _isRecording ? [
                        BoxShadow(
                          color: Colors.redAccent.withOpacity(0.5 * _pulseController.value),
                          blurRadius: 50,
                          spreadRadius: 20 * _pulseController.value,
                        )
                      ] : [],
                    ),
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            _isRecording ? Icons.mic : Icons.mic_none,
                            size: 64,
                            color: _isRecording ? Colors.redAccent : Colors.greenAccent,
                          ),
                          const SizedBox(height: 10),
                          Text(
                            _isRecording ? 'RECORDING' : 'READY',
                            style: TextStyle(
                              color: _isRecording ? Colors.redAccent : Colors.greenAccent,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 2,
                            ),
                          )
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            
            const Spacer(),
            
            // Location Info Card
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.location_on, color: Colors.blueAccent, size: 32),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('CURRENT LOCATION', style: TextStyle(color: Colors.white54, fontSize: 12, letterSpacing: 1)),
                        const SizedBox(height: 4),
                        Text(
                          _currentPosition != null 
                              ? '${_currentPosition!.latitude.toStringAsFixed(4)}, ${_currentPosition!.longitude.toStringAsFixed(4)}'
                              : 'Acquiring GPS...',
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
              padding: const EdgeInsets.only(bottom: 32.0, left: 24, right: 24),
              child: SizedBox(
                width: double.infinity,
                height: 60,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isRecording ? Colors.redAccent : Colors.greenAccent.shade400,
                    foregroundColor: _isRecording ? Colors.white : Colors.black,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
                    elevation: 5,
                  ),
                  onPressed: _toggleRecording,
                  child: Text(
                    _isRecording ? 'STOP MAPPING' : 'START MAPPING',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, letterSpacing: 1.5),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
