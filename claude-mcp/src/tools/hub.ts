/**
 * hub.ts - File-persistent message bus implementation for Agent Hub
 * This allows multiple stdio-based MCP server instances to share state.
 */

import { v4 as uuidv4 } from 'uuid';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';

const HUB_STATE_FILE = join(process.cwd(), '_handoff', 'hub_state.json');

interface Message {
    id: string;
    type: string;
    from: string;
    to: string;
    payload: any;
    timestamp: string;
}

interface Heartbeat {
    agent_id: string;
    progress: string;
    timestamp: string;
}

interface HubState {
    messages: Message[];
    heartbeats: Record<string, Heartbeat>;
    agents: string[];
}

class MessageHub {
    private loadState(): HubState {
        if (existsSync(HUB_STATE_FILE)) {
            try {
                return JSON.parse(readFileSync(HUB_STATE_FILE, 'utf-8'));
            } catch (e) {
                return { messages: [], heartbeats: {}, agents: [] };
            }
        }
        return { messages: [], heartbeats: {}, agents: [] };
    }

    private saveState(state: HubState) {
        // Ensure directory exists
        const dir = join(process.cwd(), '_handoff');
        if (!existsSync(dir)) {
            const { mkdirSync } = require('fs');
            mkdirSync(dir, { recursive: true });
        }
        writeFileSync(HUB_STATE_FILE, JSON.stringify(state, null, 2));
    }

    connect(agent_id: string) {
        const state = this.loadState();
        if (!state.agents.includes(agent_id)) {
            state.agents.push(agent_id);
            this.saveState(state);
        }
        return { success: true };
    }

    sendMessage(message: any) {
        const state = this.loadState();
        const msg: Message = {
            id: message.id || uuidv4(),
            type: message.type,
            from: message.from,
            to: message.to,
            payload: message.payload,
            timestamp: message.timestamp || new Date().toISOString()
        };
        state.messages.push(msg);
        this.saveState(state);
        return { success: true, id: msg.id };
    }

    receiveMessages(agent_id: string, since?: string) {
        const state = this.loadState();
        let msgs = state.messages.filter(m => m.to === agent_id);

        if (since) {
            const sinceDate = new Date(since);
            msgs = msgs.filter(m => new Date(m.timestamp) > sinceDate);
        }

        return { success: true, messages: msgs };
    }

    heartbeat(agent_id: string, progress: string, timestamp?: string) {
        const state = this.loadState();
        const hb: Heartbeat = {
            agent_id,
            progress,
            timestamp: timestamp || new Date().toISOString()
        };
        state.heartbeats[agent_id] = hb;
        this.saveState(state);
        return { success: true };
    }

    sendAnswer(from: string, payload: any) {
        const { question_id, selected_option } = payload;
        return this.sendMessage({
            from,
            to: 'super_manager',
            type: 'ANSWER',
            payload: { question_id, selected_option }
        });
    }
}

export const hub = new MessageHub();

export async function hubConnect(args: any) {
    return hub.connect(args.agent_id);
}

export async function hubSendMessage(args: any) {
    return hub.sendMessage(args.message);
}

export async function hubReceiveMessages(args: any) {
    return hub.receiveMessages(args.agent_id, args.since);
}

export async function hubHeartbeat(args: any) {
    return hub.heartbeat(args.agent_id, args.progress, args.timestamp);
}

export async function hubSendAnswer(args: any) {
    return hub.sendAnswer(args.from, args.payload);
}

export async function hubGetAllMessages(args: any) {
    return { messages: (hub as any).loadState().messages };
}
