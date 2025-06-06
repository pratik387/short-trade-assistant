export default function LoadingOverlay() {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-white bg-opacity-70 z-50">
      <div className="flex flex-col items-center space-y-4">
        <div className="w-12 h-12 border-4 border-blue-400 border-dashed rounded-full animate-spin"></div>
        <div className="text-blue-700 font-medium">Processing suggestions...</div>
      </div>
    </div>
  );
}