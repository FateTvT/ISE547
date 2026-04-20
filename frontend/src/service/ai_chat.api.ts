import {
  deleteSessionApiV1AiChatSessionsSessionIdDelete,
  getSessionApiV1AiChatSessionsSessionIdGet,
  listSessionsApiV1AiChatSessionsGet,
  streamChatApiV1AiChatStreamPost,
} from '../client/sdk.gen';
import type { SessionDetailResponse, SessionResponse } from '../client/types.gen';
import {
  AI_CHAT_STREAM_EVENT,
  type AiChatDiagnosisDownEventPayload,
  type AiChatErrorEventPayload,
  type AiChatInterruptEventPayload,
  type AiChatQuestionChoice,
  type AiChatMessageEventPayload,
  type AiChatQuestionCard,
  type AiChatStreamEventType,
} from '../schema/ai_chat_stream.schema';

export type MockStreamMessage = AiChatMessageEventPayload;
export type MockStreamError = AiChatErrorEventPayload;
export type MockStreamInterrupt = AiChatInterruptEventPayload;
export type MockDiagnosisDown = AiChatDiagnosisDownEventPayload;
export type PatientSex = 'male' | 'female' | 'undefine';

export type ParsedStreamEvent =
  | {
      type: typeof AI_CHAT_STREAM_EVENT.MESSAGE;
      payload: MockStreamMessage;
    }
  | {
      type: typeof AI_CHAT_STREAM_EVENT.ERROR;
      payload: MockStreamError;
    }
  | {
      type: typeof AI_CHAT_STREAM_EVENT.INTERRUPT;
      payload: MockStreamInterrupt;
    }
  | {
      type: typeof AI_CHAT_STREAM_EVENT.DIAGNOSIS_DOWN;
      payload: MockDiagnosisDown;
    };

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

function isEventType(value: unknown): value is AiChatStreamEventType {
  return (
    value === AI_CHAT_STREAM_EVENT.MESSAGE ||
    value === AI_CHAT_STREAM_EVENT.ERROR ||
    value === AI_CHAT_STREAM_EVENT.INTERRUPT ||
    value === AI_CHAT_STREAM_EVENT.DIAGNOSIS_DOWN
  );
}

function isMockStreamMessage(value: unknown): value is MockStreamMessage {
  if (!isRecord(value)) {
    return false;
  }

  return typeof value.index === 'number' && typeof value.message === 'string';
}

function isMockStreamError(value: unknown): value is MockStreamError {
  if (!isRecord(value)) {
    return false;
  }

  return typeof value.message === 'string';
}

function isMockStreamInterrupt(value: unknown): value is MockStreamInterrupt {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.question === 'string' &&
    Array.isArray(value.question_choices) &&
    value.question_choices.every(isQuestionChoice)
  );
}

function isDiagnosisDown(value: unknown): value is MockDiagnosisDown {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.diagnosis_completed === 'boolean';
}

function isQuestionChoice(value: unknown): value is AiChatQuestionChoice {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.choice_id === 'string' &&
    typeof value.choice === 'string' &&
    typeof value.selected === 'boolean'
  );
}

function toQuestionCardFromString(value: string): AiChatQuestionCard {
  return {
    question: value,
    question_choices: [
      {
        choice_id: 'free-text',
        choice: value,
        selected: false,
      },
    ],
  };
}

function parseMaybeJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

export function parseMockStreamChunk(chunk: unknown): MockStreamMessage | null {
  const parsed = parseStreamEventChunk(chunk);
  if (!parsed || parsed.type !== AI_CHAT_STREAM_EVENT.MESSAGE) {
    return null;
  }
  return parsed.payload;
}

export function parseStreamEventChunk(chunk: unknown): ParsedStreamEvent | null {
  if (isMockStreamMessage(chunk)) {
    return {
      type: AI_CHAT_STREAM_EVENT.MESSAGE,
      payload: chunk,
    };
  }

  if (isRecord(chunk) && 'data' in chunk) {
    const eventType = isEventType(chunk.event) ? chunk.event : null;
    const parsedData =
      typeof chunk.data === 'string' ? parseMaybeJson(chunk.data) : chunk.data;

    if (eventType === AI_CHAT_STREAM_EVENT.ERROR) {
      if (isMockStreamError(parsedData)) {
        return {
          type: AI_CHAT_STREAM_EVENT.ERROR,
          payload: parsedData,
        };
      }
      if (typeof parsedData === 'string') {
        return {
          type: AI_CHAT_STREAM_EVENT.ERROR,
          payload: { message: parsedData },
        };
      }
      return null;
    }

    if (eventType === AI_CHAT_STREAM_EVENT.INTERRUPT) {
      if (isMockStreamInterrupt(parsedData)) {
        return {
          type: AI_CHAT_STREAM_EVENT.INTERRUPT,
          payload: parsedData,
        };
      }
      if (typeof parsedData === 'string') {
        return {
          type: AI_CHAT_STREAM_EVENT.INTERRUPT,
          payload: toQuestionCardFromString(parsedData),
        };
      }
      return null;
    }

    if (eventType === AI_CHAT_STREAM_EVENT.DIAGNOSIS_DOWN) {
      if (isDiagnosisDown(parsedData)) {
        return {
          type: AI_CHAT_STREAM_EVENT.DIAGNOSIS_DOWN,
          payload: parsedData,
        };
      }
      return {
        type: AI_CHAT_STREAM_EVENT.DIAGNOSIS_DOWN,
        payload: { diagnosis_completed: true },
      };
    }

    return parseStreamEventChunk(parsedData);
  }

  if (typeof chunk === 'string') {
    const parsed = parseMaybeJson(chunk);
    return parseStreamEventChunk(parsed);
  }

  return null;
}

export async function createMockChatStream(
  signal: AbortSignal,
  message?: string,
  sessionId?: string,
  resume?: string,
  age?: number,
  sex?: PatientSex,
): Promise<AsyncIterable<unknown>> {
  const body = {
    message,
    session_id: sessionId,
    resume,
    age,
    sex,
  } as unknown as NonNullable<
    Parameters<typeof streamChatApiV1AiChatStreamPost>[0]['body']
  >;

  const { stream } = await streamChatApiV1AiChatStreamPost({
    body,
    signal,
    sseMaxRetryAttempts: 1,
  });
  return stream;
}

export async function fetchSessions(): Promise<SessionResponse[]> {
  const result = await listSessionsApiV1AiChatSessionsGet();
  if (result.error || !result.data) {
    return [];
  }
  return result.data;
}

export async function fetchSessionDetail(
  sessionId: string,
): Promise<SessionDetailResponse | null> {
  const result = await getSessionApiV1AiChatSessionsSessionIdGet({
    path: { session_id: sessionId },
  });
  if (result.error || !result.data) {
    return null;
  }
  return result.data;
}

export async function deleteSession(sessionId: string): Promise<boolean> {
  const result = await deleteSessionApiV1AiChatSessionsSessionIdDelete({
    path: { session_id: sessionId },
  });
  return !result.error;
}
