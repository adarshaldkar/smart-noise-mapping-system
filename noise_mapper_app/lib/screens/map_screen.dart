import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:webview_flutter/webview_flutter.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  WebViewController? _controller;
  String? _currentUrl;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadDashboard();
  }

  Future<String> _resolveHost() async {
    final prefs = await SharedPreferences.getInstance();
    final savedIp = prefs.getString('backend_ip')?.trim();
    final fallbackHost = kIsWeb
        ? 'localhost'
        : (Platform.isAndroid ? '10.0.2.2' : 'localhost');
    return (savedIp == null || savedIp.isEmpty) ? fallbackHost : savedIp;
  }

  Future<void> _loadDashboard() async {
    final host = await _resolveHost();
    final url = 'http://$host:5000/dashboard';

    final controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) {
            if (mounted) {
              setState(() {
                _loading = false;
              });
            }
          },
          onWebResourceError: (_) {
            if (mounted) {
              setState(() {
                _loading = false;
              });
            }
          },
        ),
      )
      ..loadRequest(Uri.parse(url));

    if (mounted) {
      setState(() {
        _controller = controller;
        _currentUrl = url;
        _loading = false;
      });
    }
  }

  Future<void> _refresh() async {
    final controller = _controller;
    if (controller == null) {
      await _loadDashboard();
      return;
    }
    await controller.reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Live Map'),
        actions: [
          IconButton(
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh dashboard',
          ),
        ],
      ),
      body: _controller == null
          ? Center(
              child: _loading
                  ? const CircularProgressIndicator()
                  : const Text('Unable to load dashboard.'),
            )
          : Stack(
              children: [
                WebViewWidget(controller: _controller!),
                if (_loading)
                  const Positioned.fill(
                    child: ColoredBox(
                      color: Color(0xAA0D1117),
                      child: Center(child: CircularProgressIndicator()),
                    ),
                  ),
                if (_currentUrl != null)
                  Positioned(
                    left: 12,
                    right: 12,
                    bottom: 12,
                    child: Card(
                      color: const Color(0xCC161B22),
                      child: Padding(
                        padding: const EdgeInsets.all(10),
                        child: Text(
                          _currentUrl!,
                          style: const TextStyle(fontSize: 12, color: Colors.white70),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
    );
  }
}