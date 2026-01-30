import React from "react";
import "./custom-skeleton.css";

interface CustomSkeletonProps {
  width?: number | string;
  height?: number | string;
  style?: React.CSSProperties;
  className?: string;
  borderRadius?: number | string;
}

export const CustomSkeleton: React.FC<CustomSkeletonProps> = ({
  width = "100%",
  height = "1.2em",
  style = {},
  className = "",
  borderRadius = 8,
}) => (
  <div
    className={`custom-skeleton ${className}`}
    style={{
      width,
      height,
      borderRadius,
      ...style,
    }}
  />
);

export default CustomSkeleton;
