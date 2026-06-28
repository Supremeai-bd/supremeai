// src/components/graph/SkillGraph.tsx
import { useEffect, useCallback } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType
} from 'reactflow';
import type { Connection, Edge } from 'reactflow';
import 'reactflow/dist/style.css';

// বাংলা মন্তব্য: এপিআই থেকে আসা ডেটার টাইপ ডিফাইন করা হচ্ছে
interface GraphData {
  nodes: { id: string; data: { label: string; category?: string } }[];
  edges: { id: string; source: string; target: string; label: string }[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function SkillGraph() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // বাংলা মন্তব্য: ব্যাকএন্ড থেকে গ্রাফ ডেটা ফেচ করার ফাংশন
  const fetchGraphData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/graph/skills`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}` // আপনার অথ টোকেন মেকানিজম (যদি থাকে)
        }
      });
      
      if (!response.ok) throw new Error('Failed to fetch graph data');
      
      const data: GraphData = await response.json();

      // বাংলা মন্তব্য: নোডগুলোকে একটি জ্যামিতিক বৃত্তাকার (Circular) লেআউটে সাজানোর লজিক
      const radius = 250;
      const centerX = 400;
      const centerY = 300;
      
      const formattedNodes = data.nodes.map((node, index) => {
        const angle = (index / data.nodes.length) * 2 * Math.PI;
        return {
          id: node.id,
          // Tailwind CSS ব্যবহার করে নোডের চমৎকার ডিজাইন
          className: 'bg-white border-2 border-indigo-500 rounded shadow-lg px-4 py-2 font-bold text-gray-800 text-sm text-center min-w-[120px]',
          data: { label: node.data.label },
          position: {
            x: centerX + radius * Math.cos(angle),
            y: centerY + radius * Math.sin(angle),
          },
        };
      });

      // বাংলা মন্তব্য: এজ বা কানেকশন লাইনের ডিজাইন (অ্যানিমেটেড লাইন)
      const formattedEdges = data.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        animated: true, // লাইনগুলো ফ্লোয়িং অ্যানিমেশন দেখাবে
        style: { stroke: '#6366f1', strokeWidth: 2 },
        labelStyle: { fill: '#4b5563', fontWeight: 600, fontSize: 12 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#6366f1',
        },
      }));

      setNodes(formattedNodes);
      setEdges(formattedEdges);
    } catch (error) {
      console.error("Error loading knowledge graph:", error);
    }
  };

  useEffect(() => {
    fetchGraphData();
  }, []);

  const onConnect = useCallback(
    (params: Connection | Edge) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <div className="w-full h-[600px] border border-gray-200 rounded-xl overflow-hidden shadow-inner bg-slate-50 relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
        attributionPosition="bottom-right"
      >
        {/* বাংলা মন্তব্য: ইউজার যেন গ্রাফ জুম করতে এবং মিনিম্যাপ দেখতে পারে */}
        <Background color="#ccc" gap={16} />
        <Controls />
        <MiniMap 
          nodeStrokeWidth={3} 
          nodeColor="#6366f1" 
          maskColor="rgba(240, 240, 240, 0.6)" 
        />
      </ReactFlow>
    </div>
  );
}
