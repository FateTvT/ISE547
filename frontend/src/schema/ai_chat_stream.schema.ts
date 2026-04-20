export const AI_CHAT_STREAM_EVENT = {
  MESSAGE: 'message',
  ERROR: 'error',
  INTERRUPT: 'interrupt',
  DIAGNOSIS_DOWN: 'diagnosis_down',
} as const;

export type AiChatStreamEventType =
  (typeof AI_CHAT_STREAM_EVENT)[keyof typeof AI_CHAT_STREAM_EVENT];

export type AiChatMessageEventPayload = {
  index: number;
  message: string;
};

export type AiChatErrorEventPayload = {
  message: string;
};

export type AiChatQuestionCard = {
  question: string
  question_choices: AiChatQuestionChoice[]
};

export type AiChatQuestionChoice = {
  choice_id: string
  choice: string
  selected: boolean
}

export type AiChatInterruptEventPayload = AiChatQuestionCard

export type AiChatDiagnosisDownEventPayload = {
  diagnosis_completed: boolean
}
