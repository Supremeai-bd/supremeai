import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { Github, Bot, Globe } from 'lucide-react';

const ConnectionCard = ({ icon, name, status }) => (
  <div className="flex items-center justify-between p-4 border rounded-lg">
    <div className="flex items-center gap-4">
      {icon}
      <span className="font-medium">{name}</span>
    </div>
    <div className="flex items-center gap-2">
      <span className={`text-xs font-semibold ${status === 'Connected' ? 'text-green-500' : 'text-gray-500'}`}>
        {status}
      </span>
      <Button variant="outline" size="sm">Manage</Button>
    </div>
  </div>
);

const AddConnectionModal = () => {
  const [step, setStep] = useState(1);
  const [connectionType, setConnectionType] = useState('');

  // In a real app, these would be handled by a form library like React Hook Form
  const [url, setUrl] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [apiKey, setApiKey] = useState('');

  const handleSave = async () => {
    // API call to backend: POST /api/v1/connections
    // The backend will use secure_credential_store.py to encrypt and save.
    console.log('Saving connection:', { connectionType, url, username });
    // On success, close modal and refetch connections.
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button>Add New Connection</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect a new service</DialogTitle>
        </DialogHeader>
        {step === 1 && (
          <div className="grid grid-cols-2 gap-4 py-4">
            <Button variant="outline" className="h-24 flex-col gap-2" onClick={() => { setConnectionType('website'); setStep(2); }}>
              <Globe className="h-8 w-8" />
              <span>Website Login</span>
            </Button>
            <Button variant="outline" className="h-24 flex-col gap-2" onClick={() => { setConnectionType('api'); setStep(2); }}>
              <Bot className="h-8 w-8" />
              <span>API Key</span>
            </Button>
          </div>
        )}
        {step === 2 && (
          <div className="space-y-4 py-4">
            {connectionType === 'website' && (
              <>
                <div>
                  <Label htmlFor="url">Website URL</Label>
                  <Input id="url" placeholder="https://example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
                </div>
                <div>
                  <Label htmlFor="username">Username or Email</Label>
                  <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} />
                </div>
                <div>
                  <Label htmlFor="password">Password or App Password</Label>
                  <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
                </div>
              </>
            )}
            {connectionType === 'api' && (
               <div>
                <Label htmlFor="apiKey">API Key</Label>
                <Input id="apiKey" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
              </div>
            )}
          </div>
        )}
        <DialogFooter>
          {step === 2 && <Button variant="ghost" onClick={() => setStep(1)}>Back</Button>}
          <Button onClick={handleSave} disabled={step !== 2}>Save Connection</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};


export const ConnectionsManager = () => {
  // This data would come from a backend API call: GET /api/v1/connections
  const connections = [
    { id: 1, name: 'GitHub', status: 'Connected', icon: <Github /> },
    { id: 2, name: 'My Internal Tool', status: 'Connected', icon: <Globe /> },
  ];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>My Connections</CardTitle>
        <AddConnectionModal />
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {connections.map(conn => (
            <ConnectionCard key={conn.id} {...conn} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
};