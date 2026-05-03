import 'package:flutter/material.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const NoiseMapperApp());
}

class NoiseMapperApp extends StatelessWidget {
  const NoiseMapperApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Noise Mapper',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFF121212),
        colorScheme: ColorScheme.dark(
          primary: Colors.greenAccent.shade400,
          secondary: Colors.blueAccent,
          surface: const Color(0xFF1E1E1E),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF121212),
          elevation: 0,
          centerTitle: true,
        ),
      ),
      home: const HomeScreen(),
    );
  }
}
