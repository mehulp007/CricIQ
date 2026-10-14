import Link from "next/link";

import { Scene3D } from "@/components/three/scene-3d";

export default function NotFound() {
  return (
    <div className="flex flex-col items-start gap-4 py-10">
      <Scene3D
        scene="bowled"
        poster="/3d/posters/bowled.webp"
        width={960}
        height={600}
        label="Stumps broken: the off stump knocked back, the bails on the ground and the ball at rest"
        className="w-full max-w-2xl"
      />
      <p className="font-mono text-sm text-muted-foreground">404 · Out of the ground</p>
      <h1 className="text-3xl font-semibold tracking-tight">This page doesn&apos;t exist.</h1>
      <p className="text-muted-foreground">
        It may arrive in a later milestone, or the link is wrong.
      </p>
      <Link href="/" className="text-primary underline-offset-4 hover:underline">
        Back to overview
      </Link>
    </div>
  );
}
