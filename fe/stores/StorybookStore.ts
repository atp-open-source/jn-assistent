import { Ref } from "vue";

//======= Storbook Probs ========
// JNNotatFeedback
export function TakState(
  feedbackVisible: Ref<boolean>,
  thankYouMessage: Ref<boolean>,
) {
  feedbackVisible.value = false;
  thankYouMessage.value = true;
}

// JNScaleFeedback
export function RatingState(
  storybookState: { selectedRating: number },
  refs: {
    selected: Ref<number | null>;
    feedbackMessage: Ref<string>;
    hoverMessage: Ref<string>;
    visibleScale: Ref<boolean>;
    ratingDescriptions: Record<number, string>;
  },
) {
  const { selectedRating } = storybookState;

  refs.selected.value = selectedRating;
  refs.feedbackMessage.value =
    selectedRating === 1
      ? `Du har givet dette journalnotat ${selectedRating} hjerte.`
      : `Du har givet dette journalnotat ${selectedRating} hjerter.`;

  refs.hoverMessage.value = refs.ratingDescriptions[selectedRating] || "";
  refs.visibleScale.value = false;
}
