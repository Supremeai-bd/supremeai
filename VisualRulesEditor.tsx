import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Trash2 } from 'lucide-react';

const RuleBuilder = ({ rule, onUpdate, onDelete }) => {
  return (
    <div className="flex items-center gap-2 p-2 border rounded-lg mb-2">
      <Select value={rule.condition.field} onValueChange={(v) => onUpdate({ ...rule, condition: { ...rule.condition, field: v } })}>
        <SelectTrigger className="w-[150px]"><SelectValue placeholder="Field" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="task_type">Task Type</SelectItem>
          <SelectItem value="prompt_length">Prompt Length</SelectItem>
          <SelectItem value="user_role">User Role</SelectItem>
        </SelectContent>
      </Select>
      <Select value={rule.condition.operator} onValueChange={(v) => onUpdate({ ...rule, condition: { ...rule.condition, operator: v } })}>
        <SelectTrigger className="w-[100px]"><SelectValue placeholder="Operator" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="equals">Equals</SelectItem>
          <SelectItem value="contains">Contains</SelectItem>
          <SelectItem value="gt">Greater Than</SelectItem>
        </SelectContent>
      </Select>
      <Input
        className="flex-1"
        placeholder="Value"
        value={rule.condition.value}
        onChange={(e) => onUpdate({ ...rule, condition: { ...rule.condition, value: e.target.value } })}
      />
      <span className="mx-2">THEN</span>
      <Select value={rule.action.type} onValueChange={(v) => onUpdate({ ...rule, action: { ...rule.action, type: v } })}>
        <SelectTrigger className="w-[150px]"><SelectValue placeholder="Action" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="route_to">Route To</SelectItem>
          <SelectItem value="block">Block</SelectItem>
          <SelectItem value="warn">Warn</SelectItem>
        </SelectContent>
      </Select>
      <Input
        className="flex-1"
        placeholder="Action Value"
        value={rule.action.value}
        onChange={(e) => onUpdate({ ...rule, action: { ...rule.action, value: e.target.value } })}
      />
      <Button variant="ghost" size="icon" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
};

const VisualRulesEditor = () => {
  const [rules, setRules] = useState([
    { id: 1, condition: { field: 'task_type', operator: 'equals', value: 'coding' }, action: { type: 'route_to', value: 'gpt-4-turbo' } }
  ]);

  // ... functions to add, update, delete rules and save to backend

  return (
    <Card>
      <CardHeader><CardTitle>Constitutional Rules Engine</CardTitle></CardHeader>
      <CardContent>
        {rules.map((rule, index) => <RuleBuilder key={rule.id} rule={rule} onUpdate={(newRule) => { /* update logic */ }} onDelete={() => { /* delete logic */ }} />)}
        <Button onClick={() => { /* add new rule logic */ }}>Add Rule</Button>
      </CardContent>
    </Card>
  );
};

export default VisualRulesEditor;