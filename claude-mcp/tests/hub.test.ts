import { describe, it, expect, beforeEach } from 'vitest';
import { unlinkSync, existsSync, writeFileSync } from 'fs';
import { MessageHub, HubState } from '../src/tools/hub';
import { join } from 'path';
import { tmpdir } from 'os';

describe('Hub State Management', () => {
    const TEST_STATE_FILE = join(tmpdir(), `test_hub_state_${Date.now()}.json`);
    const hub = new MessageHub();

    beforeEach(() => {
        if (existsSync(TEST_STATE_FILE)) {
            unlinkSync(TEST_STATE_FILE);
        }
    });

    it('should create empty state when file does not exist', () => {
        const state = hub.loadState(TEST_STATE_FILE);
        expect(state).toEqual({ messages: [], heartbeats: {}, agents: [] });
    });

    it('should persist messages across saves', () => {
        const state: HubState = {
            messages: [{
                id: '1',
                type: 'TEST',
                from: 'a',
                to: 'b',
                payload: {},
                timestamp: new Date().toISOString()
            }],
            heartbeats: {},
            agents: ['a', 'b']
        };

        hub.saveState(state, TEST_STATE_FILE);
        const loaded = hub.loadState(TEST_STATE_FILE);
        expect(loaded).toEqual(state);
    });

    it('should handle corrupted state file gracefully', () => {
        writeFileSync(TEST_STATE_FILE, 'not-json');
        const state = hub.loadState(TEST_STATE_FILE);
        expect(state).toEqual({ messages: [], heartbeats: {}, agents: [] });
    });
});
