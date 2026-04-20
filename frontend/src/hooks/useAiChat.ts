import { useCallback, useEffect, useRef, useState } from 'react';

import {
  createMockChatStream,
  parseStreamEventChunk,
  type PatientSex,
} from '../service/ai_chat.api';
import { AI_CHAT_STREAM_EVENT } from '../schema/ai_chat_stream.schema';
import type { AiChatQuestionCard } from '../schema/ai_chat_stream.schema';

type ChatRole = 'user' | 'assistant';
type ChatSystemRole = 'interrupt';
type ChatBubbleRole = ChatRole | ChatSystemRole;

export type ChatMessage = {
  id: string;
  role: ChatBubbleRole;
  content: string;
  questionCard?: AiChatQuestionCard;
  questionSubmitted?: boolean;
  questionReadOnly?: boolean;
};

type UseAiChatResult = {
  loading: boolean;
  err: string | null;
  inputBlocked: boolean;
  diagnosisCompleted: boolean;
  messages: ChatMessage[];
  sendMessage: (prompt: string, age: number, sex: PatientSex) => Promise<void>;
  submitSelectedQuestionChoice: (messageId: string) => Promise<void>;
  stopStream: () => void;
  setSessionId: (sessionId: string) => void;
  replaceMessages: (nextMessages: ChatMessage[]) => void;
  selectQuestionChoice: (messageId: string, choiceId: string) => void;
};

export function useAiChat(): UseAiChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [diagnosisCompleted, setDiagnosisCompleted] = useState(false);
  const [pendingInterruptMessageId, setPendingInterruptMessageId] = useState<string | null>(null);
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
    setDiagnosisCompleted(false);
    setPendingInterruptMessageId(null);
    setErr(null);
  }, []);

  const selectQuestionChoice = useCallback((messageId: string, choiceId: string) => {
    setMessages((prev) =>
      prev.map((message) => {
        if (
          message.id !== messageId ||
          message.role !== 'interrupt' ||
          !message.questionCard ||
          message.questionReadOnly
        ) {
          return message;
        }
        return {
          ...message,
          questionCard: {
            ...message.questionCard,
            question_choices: message.questionCard.question_choices.map((choice) => ({
              ...choice,
              selected: choice.choice_id === choiceId,
            })),
          },
        };
      }),
    );
  }, []);

  const sendMessage = useCallback(
    async (prompt: string, age: number, sex: PatientSex) => {
      const trimmedPrompt = prompt.trim();
      if (!trimmedPrompt || loading || pendingInterruptMessageId) {
        return;
      }

      const controller = new AbortController();
      abortControllerRef.current?.abort();
      abortControllerRef.current = controller;

      setErr(null);
      setLoading(true);
      setDiagnosisCompleted(false);
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
          undefined,
          age,
          sex,
        );

        for await (const chunk of stream) {
          const parsed = parseStreamEventChunk(chunk);
          if (!parsed) {
            continue;
          }

          if (parsed.type === AI_CHAT_STREAM_EVENT.ERROR) {
            throw new Error(parsed.payload.message);
          }

          if (parsed.type === AI_CHAT_STREAM_EVENT.INTERRUPT) {
            const interruptMessageId = `interrupt-${Date.now()}`;
            setMessages((prev) => [
              ...prev,
              {
                id: interruptMessageId,
                role: 'interrupt',
                content: parsed.payload.question,
                questionCard: parsed.payload,
                questionSubmitted: false,
                questionReadOnly: false,
              },
            ]);
            setPendingInterruptMessageId(interruptMessageId);
            continue;
          }

          if (parsed.type === AI_CHAT_STREAM_EVENT.DIAGNOSIS_DOWN) {
            setDiagnosisCompleted(parsed.payload.diagnosis_completed);
            setPendingInterruptMessageId(null);
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
                  content: parsed.payload.message,
                },
              ];
            }
            return prev.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    content: `${message.content}${parsed.payload.message}`,
                  }
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
    [loading, pendingInterruptMessageId],
  );

  const submitSelectedQuestionChoice = useCallback(
    async (messageId: string) => {
      if (loading) {
        return;
      }
      const interruptMessage = messages.find(
        (message) =>
          message.id === messageId &&
          message.role === 'interrupt' &&
          Boolean(message.questionCard),
      );
      const selectedChoiceId =
        interruptMessage?.questionCard?.question_choices.find((choice) => choice.selected)
          ?.choice_id ?? null;
      if (!selectedChoiceId) {
        setErr('Please select one option before submitting.');
        return;
      }
      setMessages((prev) =>
        prev.map((message) => {
          if (message.id !== messageId || message.role !== 'interrupt') {
            return message;
          }
          return {
            ...message,
            questionSubmitted: true,
            questionReadOnly: true,
          };
        }),
      );

      const controller = new AbortController();
      abortControllerRef.current?.abort();
      abortControllerRef.current = controller;

      setErr(null);
      setLoading(true);
      setDiagnosisCompleted(false);
      const assistantMessageId = `assistant-resume-${Date.now()}`;

      try {
        const stream = await createMockChatStream(
          controller.signal,
          undefined,
          sessionIdRef.current,
          selectedChoiceId,
        );
        for await (const chunk of stream) {
          const parsed = parseStreamEventChunk(chunk);
          if (!parsed) {
            continue;
          }

          if (parsed.type === AI_CHAT_STREAM_EVENT.ERROR) {
            throw new Error(parsed.payload.message);
          }

          if (parsed.type === AI_CHAT_STREAM_EVENT.INTERRUPT) {
            const interruptMessageId = `interrupt-${Date.now()}`;
            setMessages((prev) => [
              ...prev,
              {
                id: interruptMessageId,
                role: 'interrupt',
                content: parsed.payload.question,
                questionCard: parsed.payload,
                questionSubmitted: false,
                questionReadOnly: false,
              },
            ]);
            setPendingInterruptMessageId(interruptMessageId);
            continue;
          }

          if (parsed.type === AI_CHAT_STREAM_EVENT.DIAGNOSIS_DOWN) {
            setDiagnosisCompleted(parsed.payload.diagnosis_completed);
            setPendingInterruptMessageId(null);
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
                  content: parsed.payload.message,
                },
              ];
            }
            return prev.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    content: `${message.content}${parsed.payload.message}`,
                  }
                : message,
            );
          });
        }
        if (pendingInterruptMessageId === messageId) {
          setPendingInterruptMessageId(null);
        }
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        console.error('AI Chat resume request failed:', error);
        setErr(error instanceof Error ? error.message : 'Request failed');
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
        setLoading(false);
      }
    },
    [loading, messages, pendingInterruptMessageId],
  );

  const inputBlocked = Boolean(pendingInterruptMessageId);

  return {
    loading,
    err,
    inputBlocked,
    diagnosisCompleted,
    messages,
    sendMessage,
    submitSelectedQuestionChoice,
    stopStream,
    setSessionId,
    replaceMessages,
    selectQuestionChoice,
  };
}
