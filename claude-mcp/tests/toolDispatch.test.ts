import { describe, it, expect } from 'vitest';
import { handleToolCall } from '../src/tools';

describe('Tool Dispatcher', () => {
    it('should reject unknown tool names', async () => {
        await expect(handleToolCall('invalid_tool', {}))
            .rejects.toThrow(/Unknown tool: invalid_tool/);
    });

    it('should route to correct tool implementation', async () => {
        // claude_health doesn't require args and should return a result
        const result = await handleToolCall('claude_health', {}) as any;
        expect(result).toHaveProperty('available');
    });
});
