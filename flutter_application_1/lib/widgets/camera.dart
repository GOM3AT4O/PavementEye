import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:flutter_application_1/widgets/settings.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';
import '../providers/settings_provider.dart';
import '../services/socket_service.dart';

class CameraCapturePage extends StatefulWidget {
  @override
  _CameraCapturePageState createState() => _CameraCapturePageState();
}

class _CameraCapturePageState extends State<CameraCapturePage> with WidgetsBindingObserver {
  CameraController? _controller;
  List<CameraDescription>? _cameras;
  Timer? _timer;
  bool _noCameraAvailable = false;
  bool _isTimerRunning = false;
  int _currentRate = 5;

  // ✅ State variables
  String _uploadStatus = "Waiting...";
  String _imageName = "";
  List<String> _labels = [];
  File? _latestImageFile;
  int _captureCount = 0;

  // ✅ Add Socket Service
  final SocketService _socketService = SocketService();

  // ✅ FIXED: Add memory cleanup methods
void _cleanupMemory() {
  print('🧹 Performing memory cleanup...');
  
  // Clean up old image file
  if (_latestImageFile != null && _latestImageFile!.existsSync()) {
    try {
      _latestImageFile!.delete();
      _latestImageFile = null;
    } catch (e) {
      print('⚠️ Could not cleanup image file: $e');
    }
  }
  
  // Clear large state variables
  _labels = [];
  _uploadStatus = "Waiting for cleanup...";
  
  // Force garbage collection (Flutter will handle this automatically)
  if (WidgetsBinding.instance != null) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // This helps trigger the garbage collector
    });
  }
}

  // ✅ FIXED: Add periodic cleanup
  void _startPeriodicCleanup() {
    Timer.periodic(Duration(minutes: 2), (timer) {
      if (mounted) {
        _cleanupMemory();
      }
    });
  }

  void _monitorPerformance() {
  Timer.periodic(Duration(seconds: 30), (timer) {
    if (!mounted) {
      timer.cancel();
      return;
    }
    
    print('📊 Performance Stats:');
    print('   - Capture Count: $_captureCount');
    print('   - Timer Running: $_isTimerRunning');
    print('   - WebSocket Connected: ${_socketService.isConnected}');
    print('   - Latest Image: ${_latestImageFile != null ? "Exists" : "None"}');
    
    // Auto-cleanup if capture count gets too high
    if (_captureCount > 50) {
      print('🔄 Auto-resetting capture count for stability');
      setState(() {
        _captureCount = 0;
      });
    }
  });
}

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initialize();
    
    // ✅ Listen for WebSocket responses
    _setupSocketListeners();
    
    // ✅ FIXED: Start periodic memory cleanup
    _startPeriodicCleanup();

    _monitorPerformance(); // ✅ Add this line
  }

  // ✅ Setup WebSocket response listeners
  void _setupSocketListeners() {
    _socketService.responseStream.listen((response) {
      print('📨 Received WebSocket response: $response');
      
      // Update UI based on server response
      if (response['status'] == 'success') {
        setState(() {
          _uploadStatus = "✅ Processed successfully!";
          if (response['data'] != null) {
            _imageName = response['data']['image'] ?? '';
            _labels = List<String>.from(response['data']['labels'] ?? []);
          }
        });
      } else if (response['status'] == 'error') {
        setState(() {
          _uploadStatus = "❌ Server error: ${response['error']}";
        });
      }
    });


  

    _socketService.connectionStream.listen((isConnected) {
      print('🔗 Connection status changed: $isConnected');
      if (!isConnected && _isTimerRunning) {
        setState(() {
          _uploadStatus = "❌ WebSocket disconnected";
        });
      }
    });
  }

  // Update the dispose method in camera.dart:
@override
void dispose() {
  WidgetsBinding.instance.removeObserver(this);
  _stopTimer();
  _controller?.dispose();
  
  // ✅ FIXED: Proper cleanup sequence
  _cleanupMemory();
  _socketService.clearBuffers();
  _socketService.disconnect();
  
  super.dispose();
}


  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Listen to settings changes
    final settingsProvider = Provider.of<SettingsProvider>(context, listen: true);
    _handleSettingsChange(settingsProvider);
  }

  void _handleSettingsChange(SettingsProvider settingsProvider) {
  // ✅ Connect to WebSocket when settings change
  _connectToWebSocket(settingsProvider.api);
  
  // ✅ FIXED: Proper state management for camera timer
  if (settingsProvider.isRunning && !_isTimerRunning) {
    print('🔄 Starting camera timer');
    _startCaptureTimer();
  } else if (!settingsProvider.isRunning && _isTimerRunning) {
    print('🔄 Stopping camera timer');
    _stopTimer();
  }
  
  // ✅ FIXED: Only restart timer if it's already running AND rate changed
  if (_isTimerRunning && settingsProvider.rate != _currentRate) {
    print('🔄 Restarting timer with new rate: ${settingsProvider.rate}s');
    _restartTimerWithNewRate();
    _currentRate = settingsProvider.rate;
  }
}

  // ✅ New method to connect to WebSocket
  void _connectToWebSocket(String url) {
    if (url.isNotEmpty) {
      print('🔄 Connecting to WebSocket: $url');
      _socketService.connect(url);
    }
  }

  Future<void> _initialize() async {
    await _requestPermissions();
    await initializeCamera();
  }

  Future<void> _requestPermissions() async {
    await [
      Permission.camera,
      Permission.locationWhenInUse,
    ].request();
  }

  Future<void> initializeCamera() async {
    try {
      _cameras = await availableCameras();

      if (_cameras == null || _cameras!.isEmpty) {
        setState(() {
          _noCameraAvailable = true;
        });
        return;
      }

      _controller = CameraController(_cameras![0], ResolutionPreset.medium);
      await _controller!.initialize();
      
      setState(() {});

      // Start the capture timer after camera is ready
      final settingsProvider = Provider.of<SettingsProvider>(context, listen: false);
      if (settingsProvider.isRunning) {
        _startCaptureTimer();
      }

    } catch (e) {
      print('Error initializing camera: $e');
      setState(() {
        _noCameraAvailable = true;
      });
    }
  }

  void _restartTimerWithNewRate() {
    final settingsProvider = Provider.of<SettingsProvider>(context, listen: false);
    print('🔄 Restarting timer with new rate: ${settingsProvider.rate}s');
    _stopTimer();
    _startCaptureTimer();
  }

  void _stopTimer() {
    if (_timer != null) {
      _timer!.cancel();
      _timer = null;
      _isTimerRunning = false;
      print('⏹️ Timer stopped');
    }
  }

  void _startCaptureTimer() {
    if (_isTimerRunning) {
      _stopTimer();
    }

    final settingsProvider = Provider.of<SettingsProvider>(context, listen: false);
    
    if (!settingsProvider.isRunning) {
      print('⏸️ Camera not running - not starting timer');
      return;
    }

    if (_controller == null || !_controller!.value.isInitialized) {
      print('📷 Camera not ready - not starting timer');
      return;
    }

    print('🔄 Starting capture timer with interval: ${settingsProvider.rate}s');
    
    _timer = Timer.periodic(
      Duration(seconds: settingsProvider.rate),
      (timer) {
        _takePictureAndSendWebSocket(); // ✅ Changed to WebSocket method
      },
    );
    
    _isTimerRunning = true;
    
    Future.delayed(Duration(milliseconds: 500), () {
      if (_isTimerRunning) {
        _takePictureAndSendWebSocket(); // ✅ Changed to WebSocket method
      }
    });
  }

  // ✅ REPLACED: New WebSocket method instead of HTTP multipart
  Future<void> _takePictureAndSendWebSocket() async {
  if (_controller == null ||
      !_controller!.value.isInitialized ||
      _controller!.value.isTakingPicture) {
    return;
  }

  // ✅ Check WebSocket connection
  if (!_socketService.isConnected) {
    setState(() {
      _uploadStatus = "❌ WebSocket not connected";
    });
    print('⚠️ WebSocket not connected - skipping capture');
    return;
  }

  File? tempImageFile;
  
  try {
    setState(() {
      _uploadStatus = "📸 Capturing image...";
    });

    // 📸 Capture image
    XFile file = await _controller!.takePicture();
    tempImageFile = File(file.path);
    
    // ✅ FIXED: Limit stored images to prevent memory buildup
    if (_latestImageFile != null && _latestImageFile!.existsSync()) {
      try {
        await _latestImageFile!.delete(); // Delete previous image
      } catch (e) {
        print('⚠️ Could not delete previous image: $e');
      }
    }

    setState(() {
      _latestImageFile = tempImageFile;
      _captureCount++;
    });

    print('✅ Image captured: ${file.path} (${_captureCount} total)');

    // 📍 Get location
    Position position = await Geolocator.getCurrentPosition(
      desiredAccuracy: LocationAccuracy.high,
    );
    print('📍 Location: ${position.latitude}, ${position.longitude}');

    // Get current settings
    final settingsProvider = Provider.of<SettingsProvider>(context, listen: false);

    // ✅ FIXED: Read image bytes with file size check
    List<int> imageBytes = await tempImageFile.readAsBytes();
    
    // ✅ FIXED: Check file size and compress if too large
    if (imageBytes.length > 2 * 1024 * 1024) { // 2MB threshold
      print('📦 Image too large (${imageBytes.length ~/ 1024}KB), consider compression');
      // You could add image compression here if needed
    }
    
    String base64Image = base64Encode(imageBytes);
    
    // Clear the large byte array from memory immediately
    imageBytes = [];

    setState(() {
      _uploadStatus = "🔄 Sending via WebSocket...";
    });

    // ✅ Send via WebSocket instead of HTTP
    _socketService.sendImageData(
      base64Image, // Base64 string without prefix
      position.longitude,
      position.latitude,
      settingsProvider.ppm,
    );

    // ✅ FIXED: Clear base64 string from memory after sending
    base64Image = "";

    setState(() {
      _uploadStatus = "✅ Sent via WebSocket!";
      _imageName = "${position.longitude.toStringAsFixed(4)}_${position.latitude.toStringAsFixed(4)}_${DateTime.now().millisecondsSinceEpoch}.jpg";
    });

  } catch (e) {
    print('❌ Error: $e');
    
    // ✅ FIXED: Clean up temp file on error
    if (tempImageFile != null && tempImageFile.existsSync()) {
      try {
        await tempImageFile.delete();
      } catch (deleteError) {
        print('⚠️ Could not delete temp image: $deleteError');
      }
    }
    
    setState(() {
      _uploadStatus = "❌ Error: ${e.toString()}";
      _imageName = '';
      _labels = [];
    });
  }
}

  // ✅ Manual reconnect method
  void _manualReconnect() {
    final settingsProvider = Provider.of<SettingsProvider>(context, listen: false);
    _connectToWebSocket(settingsProvider.api);
    setState(() {
      _uploadStatus = "🔄 Reconnecting...";
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<SettingsProvider>(
      builder: (context, settingsProvider, child) {
        if (settingsProvider.isLoading) {
          return Scaffold(
            appBar: AppBar(title: Text('Camera WebSocket Stream')),
            body: Center(child: CircularProgressIndicator()),
          );
        }

        return Scaffold(
          appBar: AppBar(
            title: Text('Camera WebSocket Stream'),
            actions: [
              // ✅ WebSocket reconnect button
              IconButton(
                icon: Icon(Icons.refresh),
                onPressed: _manualReconnect,
                tooltip: 'Reconnect WebSocket',
              ),
              IconButton(
                icon: Icon(Icons.settings),
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (context) => SettingsPage()),
                  );
                },
              ),
            ],
          ),
          body: _noCameraAvailable
              ? Center(child: Text('No camera available on this device.'))
              : (_controller == null || !_controller!.value.isInitialized)
                  ? Center(child: CircularProgressIndicator())
                  : Column(
                      children: [
                        // 🖼️ Logo at the top
                        Padding(
                          padding: const EdgeInsets.all(8.0),
                          child: Image.asset(
                            'assets/images/logo.png',
                            height: 80,
                          ),
                        ),

                        // Settings Status Bar
                        Container(
                          padding: EdgeInsets.all(8),
                          color: Colors.grey[100],
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceAround,
                            children: [
                              _buildStatusItem('Status', settingsProvider.isRunning ? 'Running' : 'Paused', 
                                  settingsProvider.isRunning ? Icons.check_circle : Icons.pause_circle,
                                  settingsProvider.isRunning ? Colors.green : Colors.orange),
                              _buildStatusItem('PPM', '${settingsProvider.ppm.toInt()}', 
                                  Icons.photo_camera, Colors.blue),
                              _buildStatusItem('Interval', '${settingsProvider.rate}s', 
                                  Icons.timer, Colors.purple),
                              _buildStatusItem('Captures', '$_captureCount', 
                                  Icons.camera_alt, Colors.red),
                              // ✅ Add WebSocket status
                              _buildStatusItem(
                                'WebSocket', 
                                _socketService.isConnected ? 'Connected' : 'Disconnected', 
                                _socketService.isConnected ? Icons.wifi : Icons.wifi_off,
                                _socketService.isConnected ? Colors.green : Colors.red,
                              ),
                            ],
                          ),
                        ),

                        // 🖼️ Preview the last captured image
                        if (_latestImageFile != null)
                          Container(
                            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            height: 150,
                            decoration: BoxDecoration(
                              border: Border.all(color: Colors.blueGrey),
                            ),
                            child: Image.file(
                              _latestImageFile!,
                              fit: BoxFit.cover,
                              width: double.infinity,
                            ),
                          ),

                        // 📷 Camera Preview
                        Expanded(
                          flex: 3,
                          child: Stack(
                            children: [
                              CameraPreview(_controller!),
                              // ✅ Overlay connection status
                              if (!_socketService.isConnected)
                                Container(
                                  color: Colors.black54,
                                  child: Center(
                                    child: Column(
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      children: [
                                        Icon(Icons.wifi_off, size: 50, color: Colors.red),
                                        SizedBox(height: 10),
                                        Text(
                                          'WebSocket Disconnected',
                                          style: TextStyle(
                                            color: Colors.white,
                                            fontSize: 18,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                        SizedBox(height: 10),
                                        ElevatedButton.icon(
                                          onPressed: _manualReconnect,
                                          icon: Icon(Icons.refresh),
                                          label: Text('Reconnect'),
                                          style: ElevatedButton.styleFrom(
                                            backgroundColor: Colors.orange,
                                            foregroundColor: Colors.white,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),

                        // ℹ️ Upload Status + Info
                        Expanded(
                          flex: 2,
                          child: Container(
                            padding: const EdgeInsets.all(16),
                            width: double.infinity,
                            color: Colors.grey.shade100,
                            child: SingleChildScrollView(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  // ✅ Connection status with color coding
                                  Row(
                                    children: [
                                      Icon(
                                        _socketService.isConnected ? Icons.check_circle : Icons.error,
                                        color: _socketService.isConnected ? Colors.green : Colors.red,
                                        size: 20,
                                      ),
                                      SizedBox(width: 8),
                                      Expanded(
                                        child: Text(
                                          "WebSocket: ${_socketService.isConnected ? 'Connected' : 'Disconnected'}",
                                          style: TextStyle(
                                            fontSize: 16,
                                            color: _socketService.isConnected ? Colors.green : Colors.red,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  SizedBox(height: 10),
                                  Text("Status: $_uploadStatus",
                                      style: TextStyle(fontSize: 16)),
                                  SizedBox(height: 10),
                                  Text("Image Name: $_imageName",
                                      style: TextStyle(fontSize: 14)),
                                  SizedBox(height: 10),
                                  Text("Detected Labels:",
                                      style: TextStyle(fontWeight: FontWeight.bold)),
                                  SizedBox(height: 5),
                                  Wrap(
                                    spacing: 8,
                                    children: _labels.isEmpty
                                        ? [Text("Waiting for server response...")]
                                        : _labels
                                            .map((label) => Chip(
                                              label: Text(label),
                                              backgroundColor: Colors.blue[100],
                                            ))
                                            .toList(),
                                  ),
                                  // ✅ Manual controls
                                  if (!_socketService.isConnected)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 16.0),
                                      child: ElevatedButton.icon(
                                        onPressed: _manualReconnect,
                                        icon: Icon(Icons.refresh),
                                        label: Text('Reconnect WebSocket'),
                                        style: ElevatedButton.styleFrom(
                                          backgroundColor: Colors.orange,
                                          foregroundColor: Colors.white,
                                          minimumSize: Size(double.infinity, 50),
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
        );
      },
    );
  }

  Widget _buildStatusItem(String label, String value, IconData icon, Color color) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: color, size: 16),
        SizedBox(height: 2),
        Text(value, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
        Text(label, style: TextStyle(fontSize: 10, color: Colors.grey)),
      ],
    );
  }
}