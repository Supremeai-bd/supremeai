import React, { useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Globe, Smartphone, Tablet } from 'lucide-react';

const BrowserPreview = ({ htmlContent, cssContent, jsContent }) => {
  const iframeRef = useRef(null);
  const [view, setView] = useState('desktop');

  const viewports = {
    desktop: '100%',
    tablet: '768px',
    mobile: '375px',
  };

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const document = iframe.contentDocument;
    document.body.innerHTML = htmlContent;
    const styleElement = document.createElement('style');
    styleElement.innerHTML = cssContent;
    document.head.appendChild(styleElement);
    
    // Note: For security, JS execution should be sandboxed.
    // This is a simplified example.
    const scriptElement = document.createElement('script');
    scriptElement.innerHTML = jsContent;
    document.body.appendChild(scriptElement);

  }, [htmlContent, cssContent, jsContent]);

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Live Preview</CardTitle>
        <div className="flex gap-1">
          <Button variant={view === 'desktop' ? 'secondary' : 'ghost'} size="icon" onClick={() => setView('desktop')}><Globe className="h-4 w-4" /></Button>
          <Button variant={view === 'tablet' ? 'secondary' : 'ghost'} size="icon" onClick={() => setView('tablet')}><Tablet className="h-4 w-4" /></Button>
          <Button variant={view === 'mobile' ? 'secondary' : 'ghost'} size="icon" onClick={() => setView('mobile')}><Smartphone className="h-4 w-4" /></Button>
        </div>
      </CardHeader>
      <CardContent className="flex-grow p-0">
        <iframe
          ref={iframeRef}
          title="Live Preview"
          sandbox="allow-scripts"
          className="w-full h-full border-0 transition-all"
          style={{ width: viewports[view], margin: '0 auto' }}
        />
      </CardContent>
    </Card>
  );
};

export default BrowserPreview;