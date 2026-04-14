import { streamChatApiV1AiChatStreamPost } from '../client/sdk.gen';

export type MockStreamMessage = {
  index: number;
  message: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

function isMockStreamMessage(value: unknown): value is MockStreamMessage {
  if (!isRecord(value)) {
    return false;
  }

  return typeof value.index === 'number' && typeof value.message === 'string';
}

function parseMaybeJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

export function parseMockStreamChunk(chunk: unknown): MockStreamMessage | null {
  if (isMockStreamMessage(chunk)) {
    return chunk;
  }

  if (isRecord(chunk) && 'data' in chunk) {
    return parseMockStreamChunk(chunk.data);
  }

  if (typeof chunk === 'string') {
    const parsed = parseMaybeJson(chunk);
    if (isMockStreamMessage(parsed)) {
      return parsed;
    }

    if (isRecord(parsed) && 'data' in parsed) {
      return parseMockStreamChunk(parsed.data);
    }
  }

  return null;
}

export async function createMockChatStream(
  signal: AbortSignal,
  message: string,
  sessionId: string,
): Promise<AsyncIterable<unknown>> {
  const { stream } = await streamChatApiV1AiChatStreamPost({
    body: {
      message,
      session_id: sessionId,
    },
    signal,
    sseMaxRetryAttempts: 1,
  });
  return stream;
}
