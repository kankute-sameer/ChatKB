import { useNavigate } from "react-router-dom";
import { Composer } from "@/components/ChatView";
import { LandingHero } from "@/components/LandingHero";
import {
  createConversation,
  notifyConversationsChanged,
} from "@/lib/conversations";

export function ChatHomePage() {
  const navigate = useNavigate();

  const onSubmit = async (text: string) => {
    const conversation = await createConversation();
    notifyConversationsChanged();
    navigate(`/c/${conversation.id}`, { state: { pendingText: text } });
  };

  return (
    <LandingHero
      title="What can your agents help with?"
      composer={
        <Composer
          placeholder="Ask anything..."
          onSubmit={(text) => {
            void onSubmit(text);
          }}
        />
      }
    />
  );
}
