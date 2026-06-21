// Web Worker for parsing large JSON/log data without blocking main thread
self.onmessage = function(e) {
  const { action, data } = e.data;
  
  switch (action) {
    case 'PARSE_LOGS':
      const lines = data.split('\n');
      const parsed = lines.map((line: string, index: number) => {
        try {
          if (line.includes('"') && line.includes(',')) {
            return JSON.parse(line);
          }
          return { raw: line, lineNumber: index };
        } catch {
          return { raw: line, lineNumber: index };
        }
      }).filter(Boolean);
      self.postMessage({ action: 'LOGS_PARSED', result: parsed });
      break;
      
    case 'PARSE_LARGE_JSON':
      try {
        const parsed = JSON.parse(data);
        self.postMessage({ action: 'JSON_PARSED', result: parsed });
      } catch (err) {
        self.postMessage({ action: 'PARSE_ERROR', error: err instanceof Error ? err.message : String(err) });
      }
      break;
      
    case 'SEARCH_LOGS':
      const { logs, query } = e.data.payload;
      const results = logs.filter((log: any) => 
        log.raw?.toLowerCase().includes(query.toLowerCase()) ||
        log.message?.toLowerCase().includes(query.toLowerCase())
      );
      self.postMessage({ action: 'SEARCH_RESULTS', result: results });
      break;
      
    default:
      self.postMessage({ action: 'UNKNOWN', error: 'Unknown action: ' + action });
  }
};