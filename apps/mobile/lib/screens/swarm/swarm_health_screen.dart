import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../theme/tokens.dart'; // Adjust path
import '../../widgets/supreme_ui/supreme_card.dart';
import '../../services/api_client.dart';
import 'hold_to_kill_button.dart';

// বাংলা মন্তব্য: আগে এই স্ক্রিনের সব ডেটা (CPU/Memory/Agent/Log) Timer.periodic +
// Random() দিয়ে তৈরি হতো — ব্যাকএন্ডের সাথে কোনো সংযোগ ছিল না, এবং "Hold to Kill"
// বাটন শুধু লোকাল state বদলাত, আসলে কোনো এজেন্ট থামত না। এখন এটি সত্যিকারের
// /api/v1/swarm/stream SSE ফিড কনজিউম করে এবং /api/v1/swarm/halt কে সত্যিই কল করে।
class SwarmHealthScreen extends StatefulWidget {
  final String baseUrl;

  const SwarmHealthScreen({super.key, this.baseUrl = ApiClient.baseUrl});

  @override
  State<SwarmHealthScreen> createState() => _SwarmHealthScreenState();
}

class _SwarmHealthScreenState extends State<SwarmHealthScreen> {
  final ApiClient _apiClient = ApiClient();
  http.Client? _httpClient;
  StreamSubscription<String>? _sseSubscription;

  String _circuitState = 'CLOSED';
  final Set<String> _runningAgentIds = {};
  final List<Map<String, dynamic>> _logs = [];
  bool _isConnected = false;
  bool _isHalting = false;

  @override
  void initState() {
    super.initState();
    _connectToSwarmStream();
  }

  // বাংলা মন্তব্য: sse_starlette ব্যাকএন্ডে EventSourceResponse ব্যবহার করে, যা
  // "data: <json>\n\n" ফরম্যাটে ইভেন্ট পাঠায়। এখানে নতুন কোনো প্যাকেজ যোগ না করে
  // http প্যাকেজের streamed request দিয়ে manually SSE লাইন পার্স করা হচ্ছে।
  void _connectToSwarmStream() {
    _httpClient = http.Client();
    final request = http.Request('GET', Uri.parse('${widget.baseUrl}/api/v1/swarm/stream'));
    request.headers['Accept'] = 'text/event-stream';

    _httpClient!.send(request).then((streamedResponse) {
      if (!mounted) return;
      setState(() => _isConnected = streamedResponse.statusCode == 200);

      _sseSubscription = streamedResponse.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .listen(
        _handleSseLine,
        onError: (_) => _scheduleReconnect(),
        onDone: _scheduleReconnect,
        cancelOnError: true,
      );
    }).catchError((_) {
      if (mounted) setState(() => _isConnected = false);
      _scheduleReconnect();
    });
  }

  void _scheduleReconnect() {
    if (!mounted) return;
    setState(() => _isConnected = false);
    Future.delayed(const Duration(seconds: 3), () {
      if (mounted) _connectToSwarmStream();
    });
  }

  void _handleSseLine(String line) {
    if (!line.startsWith('data:')) return;
    final raw = line.substring(5).trim();
    if (raw.isEmpty) return;

    try {
      final envelope = json.decode(raw) as Map<String, dynamic>;
      final eventType = envelope['type'] as String?;
      final payload = (envelope['data'] as Map<String, dynamic>?) ?? {};

      setState(() {
        switch (eventType) {
          case 'NODE_EXECUTION':
            final nodeId = payload['nodeId']?.toString();
            final status = payload['status']?.toString();
            if (nodeId != null) {
              if (status == 'RUNNING') {
                _runningAgentIds.add(nodeId);
              } else {
                _runningAgentIds.remove(nodeId);
              }
            }
            _pushLog(agent: nodeId ?? 'AGENT', message: payload['message']?.toString() ?? '', level: 'info');
            break;
          case 'CIRCUIT_OPEN':
            _circuitState = 'OPEN';
            _pushLog(agent: 'SYSTEM', message: payload['message']?.toString() ?? 'Circuit breaker OPEN', level: 'error');
            break;
          case 'CIRCUIT_CLOSED':
            _circuitState = 'CLOSED';
            _pushLog(agent: 'SYSTEM', message: payload['message']?.toString() ?? 'Circuit breaker CLOSED', level: 'info');
            break;
          case 'DEBATE_UPDATE':
            _pushLog(agent: 'DEBATE', message: 'state=${payload['state']}', level: 'info');
            break;
          default:
            if (eventType != null) {
              _pushLog(agent: eventType, message: payload.toString(), level: 'info');
            }
        }
      });
    } catch (_) {
      // বাংলা মন্তব্য: ম্যালফর্মড ইভেন্ট সাইলেন্টলি ড্রপ করা হয় — ফিড ক্র্যাশ করা উচিত না।
    }
  }

  void _pushLog({required String agent, required String message, required String level}) {
    _logs.insert(0, {'agent': agent, 'message': message, 'level': level, 'time': DateTime.now()});
    if (_logs.length > 50) _logs.removeLast();
  }

  Future<void> _triggerCircuitBreaker() async {
    if (_isHalting) return;
    setState(() => _isHalting = true);

    final success = await _apiClient.haltSwarm();

    if (!mounted) return;
    setState(() {
      _isHalting = false;
      if (!success) {
        _pushLog(
          agent: 'SYSTEM',
          message: 'Emergency stop request failed — check admin login/network.',
          level: 'error',
        );
      }
      // বাস্তব _circuitState আপডেট SSE ফিড থেকে CIRCUIT_OPEN ইভেন্ট আসার পরই হবে,
      // এখানে জোর করে UI-তে "OPEN" ধরে নেওয়া হচ্ছে না।
    });
  }

  @override
  void dispose() {
    _sseSubscription?.cancel();
    _httpClient?.close();
    super.dispose();
  }

  Widget _buildMetricCard(String title, String value, String unit) {
    return SupremeCard(
      child: Padding(
        padding: const EdgeInsets.all(DesignTokens.space4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              title,
              style: TextStyle(
                color: DesignTokens.textSecondaryDark,
                fontSize: DesignTokens.fontSizeSm,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  value,
                  style: TextStyle(
                    color: DesignTokens.textPrimaryDark,
                    fontSize: DesignTokens.fontSize2xl,
                    fontWeight: FontWeight.bold,
                    fontFamily: DesignTokens.fontFamilyMono,
                  ),
                ),
                const SizedBox(width: 4),
                Text(
                  unit,
                  style: TextStyle(
                    color: DesignTokens.brandPrimaryDark,
                    fontSize: DesignTokens.fontSizeXs,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DesignTokens.bgVoidDark,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: Text(
          'Swarm Health',
          style: TextStyle(
            fontFamily: DesignTokens.fontFamilyDisplay,
            color: DesignTokens.textPrimaryDark,
          ),
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(
              child: Row(
                children: [
                  Icon(
                    _isConnected ? Icons.circle : Icons.circle_outlined,
                    size: 10,
                    color: _isConnected ? Colors.greenAccent : DesignTokens.textSecondaryDark,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    _isConnected ? 'LIVE' : 'RECONNECTING',
                    style: TextStyle(fontSize: 10, color: DesignTokens.textSecondaryDark),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(DesignTokens.space4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // বাংলা মন্তব্য: CPU/Memory/Error-Rate-এর জন্য ব্যাকএন্ডে এখনো কোনো
              // real telemetry broadcaster নেই (শুধু agent execution events আছে),
              // তাই fake সংখ্যা না দেখিয়ে honestly "N/A" দেখানো হচ্ছে। শুধু
              // Active Agents আসল ইভেন্ট থেকে গণনা করা।
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                mainAxisSpacing: DesignTokens.space3,
                crossAxisSpacing: DesignTokens.space3,
                childAspectRatio: 1.5,
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  _buildMetricCard('CPU Load', 'N/A', ''),
                  _buildMetricCard('Memory', 'N/A', ''),
                  _buildMetricCard('Active Agents', '${_runningAgentIds.length}', 'NODES'),
                  _buildMetricCard('Circuit', _circuitState, ''),
                ],
              ),
              const SizedBox(height: DesignTokens.space6),

              Text(
                'LIVE EXECUTION FEED',
                style: TextStyle(
                  color: DesignTokens.textSecondaryDark,
                  fontSize: DesignTokens.fontSizeSm,
                  letterSpacing: 1.2,
                ),
              ),
              const SizedBox(height: DesignTokens.space2),
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: DesignTokens.bgElevatedDark,
                    borderRadius: BorderRadius.circular(DesignTokens.radiusMd),
                    border: Border.all(color: DesignTokens.borderDefaultDark),
                  ),
                  child: _logs.isEmpty
                      ? Center(
                          child: Text(
                            _isConnected ? 'Waiting for swarm activity…' : 'Connecting to swarm stream…',
                            style: TextStyle(color: DesignTokens.textSecondaryDark, fontSize: DesignTokens.fontSizeXs),
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.all(DesignTokens.space3),
                          itemCount: _logs.length,
                          itemBuilder: (context, index) {
                            final log = _logs[index];
                            final isError = log['level'] == 'error';
                            return Padding(
                              padding: const EdgeInsets.only(bottom: 8.0),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '[${log['agent']}]',
                                    style: TextStyle(
                                      color: isError ? DesignTokens.brandDangerDark : DesignTokens.brandSecondaryDark,
                                      fontFamily: DesignTokens.fontFamilyMono,
                                      fontSize: DesignTokens.fontSizeXs,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      log['message'],
                                      style: TextStyle(
                                        color: isError ? DesignTokens.brandDangerDark : DesignTokens.textPrimaryDark,
                                        fontFamily: DesignTokens.fontFamilyMono,
                                        fontSize: DesignTokens.fontSizeXs,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                ),
              ),
              const SizedBox(height: DesignTokens.space6),

              HoldToKillButton(
                onTrigger: _triggerCircuitBreaker,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
