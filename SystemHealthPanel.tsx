import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useQuery } from '@tanstack/react-query';

// Mock API call - replace with your actual API endpoint
const fetchHealthMetrics = async () => {
  // In a real app, this would fetch from /admin-api/health-metrics
  // For now, we simulate live data
  return {
    cpuUsage: Math.random() * 100,
    memoryUsage: Math.random() * 80 + 10,
    activeRequests: Math.floor(Math.random() * 200),
    p95Latency: Math.floor(Math.random() * 300) + 50,
  };
};

const SystemHealthPanel = () => {
  const [chartData, setChartData] = useState([]);

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['systemHealth'],
    queryFn: fetchHealthMetrics,
    refetchInterval: 2000, // Refetch every 2 seconds
  });

  useEffect(() => {
    if (metrics) {
      const newEntry = {
        time: new Date().toLocaleTimeString(),
        cpu: metrics.cpuUsage.toFixed(2),
        memory: metrics.memoryUsage.toFixed(2),
      };
      setChartData(prevData => [...prevData.slice(-29), newEntry]);
    }
  }, [metrics]);

  if (isLoading) return <Card><CardHeader><CardTitle>Loading System Health...</CardTitle></CardHeader></Card>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>System Heartbeat (Live)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 text-center">
          <div><p className="text-sm text-muted-foreground">CPU Usage</p><p className="text-2xl font-bold">{metrics?.cpuUsage.toFixed(1)}%</p></div>
          <div><p className="text-sm text-muted-foreground">Memory</p><p className="text-2xl font-bold">{metrics?.memoryUsage.toFixed(1)}%</p></div>
          <div><p className="text-sm text-muted-foreground">Active Requests</p><p className="text-2xl font-bold">{metrics?.activeRequests}</p></div>
          <div><p className="text-sm text-muted-foreground">P95 Latency</p><p className="text-2xl font-bold">{metrics?.p95Latency}ms</p></div>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <XAxis dataKey="time" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip wrapperClassName="!bg-background !border-border" />
            <Legend />
            <Line type="monotone" dataKey="cpu" stroke="#8884d8" strokeWidth={2} dot={false} name="CPU (%)" />
            <Line type="monotone" dataKey="memory" stroke="#82ca9d" strokeWidth={2} dot={false} name="Memory (%)" />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

export default SystemHealthPanel;