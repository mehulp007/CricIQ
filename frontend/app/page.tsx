import { LandingPage } from "@/components/landing/landing-page";
import { landingData } from "@/lib/landing";

export default function HomePage() {
  return <LandingPage {...landingData()} />;
}
