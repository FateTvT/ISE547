import { useCallback, useEffect, useRef, useState } from 'react';

import {
  createMockChatStream,
  parseMockStreamChunk,
} from '../service/ai_chat.api';

type ChatRole = 'user' | 'assistant';

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
};

type UseAiChatResult = {
  loading: boolean;
  err: string | null;
  messages: ChatMessage[];
  sendMessage: (prompt: string) => Promise<void>;
  stopStream: () => void;
  setSessionId: (sessionId: string) => void;
  replaceMessages: (nextMessages: ChatMessage[]) => void;
};

export function useAiChat(): UseAiChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef(`session-${Date.now()}`);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const stopStream = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setLoading(false);
  }, []);

  const setSessionId = useCallback((sessionId: string) => {
    sessionIdRef.current = sessionId;
  }, []);

  const replaceMessages = useCallback((nextMessages: ChatMessage[]) => {
    setMessages(nextMessages);
    setErr(null);
  }, []);

  const sendMessage = useCallback(
    async (prompt: string) => {
      const trimmedPrompt = prompt.trim();
      if (!trimmedPrompt || loading) {
        return;
      }

      const controller = new AbortController();
      abortControllerRef.current?.abort();
      abortControllerRef.current = controller;

      setErr(null);
      setLoading(true);
      const userMessageId = `user-${Date.now()}`;
      const assistantMessageId = `assistant-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: userMessageId,
          role: 'user',
          content: trimmedPrompt,
        },
      ]);

      try {
        const stream = await createMockChatStream(
          controller.signal,
          trimmedPrompt,
          sessionIdRef.current,
        );

        for await (const chunk of stream) {
          const parsed = parseMockStreamChunk(chunk);
          if (!parsed) {
            continue;
          }

          setMessages((prev) => {
            const existingMessageIndex = prev.findIndex(
              (message) => message.id === assistantMessageId,
            );
            if (existingMessageIndex < 0) {
              return [
                ...prev,
                {
                  id: assistantMessageId,
                  role: 'assistant',
                  content: parsed.message,
                },
              ];
            }
            return prev.map((message) =>
              message.id === assistantMessageId
                ? { ...message, content: `${message.content}${parsed.message}` }
                : message,
            );
          });
        }
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }

        console.error('AI Chat streaming request failed:', error);
        setErr(error instanceof Error ? error.message : 'Request failed');
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
        setLoading(false);
      }
    },
    [loading],
  );

  return {
    loading,
    err,
    messages,
    sendMessage,
    stopStream,
    setSessionId,
    replaceMessages,
  };
}
