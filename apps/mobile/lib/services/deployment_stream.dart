import 'dart:async';
import 'byoc_service.dart';

class DeploymentStream {
  final ByocService _byocService;
  StreamController<Map<String, dynamic>>? _controller;
  Timer? _timer;

  DeploymentStream({ByocService? byocService}) : _byocService = byocService ?? ByocService();

  /// Starts polling the status endpoint using Exponential Backoff to optimize battery and servers.
  Stream<Map<String, dynamic>> monitorDeployment(String jobId) {
    _controller = StreamController<Map<String, dynamic>>.broadcast();

    // Initial delays configuration
    int currentDelaySeconds = 1;
    const int maxDelaySeconds = 16;

    // বাংলা মন্তব্য: এক্সপোনেনশিয়াল ব্যাকঅফ পোলিং মেকানিজম - ব্যাটারি ও সার্ভার লোড হ্রাসে সাহায্য করে।
    void pollNext() {
      _timer = Timer(Duration(seconds: currentDelaySeconds), () async {
        if (_controller == null || _controller!.isClosed) return;

        final res = await _byocService.getDeploymentStatus(jobId);
        if (res['success'] == true) {
          final job = res['job'];
          _controller?.add(job);

          final String status = job['status'] ?? 'pending';
          if (status == 'success' || status == 'failed') {
            // Terminate stream immediately when terminal state is reached
            _controller?.close();
            return;
          }

          // Exponential backoff multiplier
          currentDelaySeconds = (currentDelaySeconds * 2).clamp(1, maxDelaySeconds);
        } else {
          _controller?.addError(res['error'] ?? 'Unknown error occurred.');
          _controller?.close();
          return;
        }

        // Loop execution recursively with updated exponential backoff delay
        pollNext();
      });
    }

    pollNext();
    return _controller!.stream;
  }

  void cancel() {
    _timer?.cancel();
    _controller?.close();
  }
}
