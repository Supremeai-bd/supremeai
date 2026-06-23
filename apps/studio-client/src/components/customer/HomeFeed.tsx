// ============================================================================
// component >> HomeFeed.tsx
// project >> SupremeAI 2.0
// purpose >> General utility
// module >> src
// ============================================================================
interface Widget {
  id: string;
  title: string;
  content: string;
}

const initialWidgets: Widget[] = [
  { id: '1', title: 'AI Assistant', content: 'Chat with your AI assistant to get help with coding, debugging, and more.' },
  { id: '2', title: 'Code Snippets', content: 'Save and reuse your favorite code snippets.' },
  { id: '3', title: 'Project Stats', content: 'View statistics about your current project.' },
  { id: '4', title: 'Quick Commands', content: 'Execute common commands with one click.' },
  { id: '5', title: 'Resource Monitor', content: 'Monitor CPU, memory, and network usage.' },
  { id: '6', title: 'Latest News', content: 'Stay updated with the latest AI and tech news.' },
];

export function HomeFeed() {
  const [widgets, setWidgets] = useState<Widget[]>(initialWidgets);

  const handleDragStart = (e: React.DragEvent<HTMLDivElement>, id: string) => {
    e.dataTransfer.setData('text/plain', id);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>, dropId: string) => {
    e.preventDefault();
    const draggedId = e.dataTransfer.getData('text/plain');
    if (draggedId === dropId) return;

    setWidgets(prev => {
      const draggedIndex = prev.findIndex(w => w.id === draggedId);
      const dropIndex = prev.findIndex(w => w.id === dropId);
      if (draggedIndex === -1 || dropIndex === -1) return prev;

      const newWidgets = [...prev];
      const [draggedWidget] = newWidgets.splice(draggedIndex, 1);
      newWidgets.splice(dropIndex, 0, draggedWidget);
      return newWidgets;
    });
  };

  return (
    <div className="p-4 bg-[#020205] min-h-[calc(100vh-64px)] overflow-y-auto">
      <h2 className="text-2xl font-bold font-['Space_Grotesk'] tracking-widest mb-6 text-[#f8f9fa]">
        Personalized Home Feed
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {widgets.map(widget => (
          <div
            key={widget.id}
            draggable
            onDragStart={(e) => handleDragStart(e, widget.id)}
            onDragOver={(e) => handleDragOver(e)}
            onDrop={(e) => handleDrop(e, widget.id)}
            className="glass-card cursor-move p-4 flex flex-col gap-3 hover:shadow-lg transition-shadow"
          >
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--neon-blue)]/10 text-[var(--neon-blue)]">
                {/* Icon placeholder */}
                <span className="text-[var(--neon-blue)]">🤖</span>
              </div>
              <h3 className="font-semibold text-[var(--foreground)]">{widget.title}</h3>
            </div>
            <p className="text-[var(--foreground)]/70 text-sm flex-1">{widget.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}