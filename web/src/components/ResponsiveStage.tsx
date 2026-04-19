import { useState, useRef, useLayoutEffect, type ReactNode } from "react";
import { Stage, Layer } from "react-konva";

interface ResponsiveStageProps {
  children: ReactNode;
  sceneWidth?: number;
  sceneHeight?: number;
}

export function ResponsiveStage({
  children,
  sceneWidth = 1800,
  sceneHeight = 1300,
}: ResponsiveStageProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [stageSize, setStageSize] = useState({
    width: sceneWidth,
    height: sceneHeight,
    scale: 1,
  });

  useLayoutEffect(() => {
    const updateSize = () => {
      if (!containerRef.current) return;

      const containerWidth = containerRef.current.clientWidth;
      const containerHeight = containerRef.current.clientHeight;

      const scaleX = containerWidth / sceneWidth;
      const scaleY = containerHeight / sceneHeight;
      const scale = Math.min(scaleX, scaleY);

      setStageSize({
        width: sceneWidth * scale,
        height: sceneHeight * scale,
        scale: scale,
      });
    };

    updateSize();
    window.addEventListener("resize", updateSize);

    return () => {
      window.removeEventListener("resize", updateSize);
    };
  }, [sceneWidth, sceneHeight]);

  return (
    <div ref={containerRef} className="w-full h-full max-h-full">
      <Stage
        width={stageSize.width}
        height={stageSize.height}
        scaleX={stageSize.scale}
        scaleY={stageSize.scale}
      >
        <Layer>{children}</Layer>
      </Stage>
    </div>
  );
}
