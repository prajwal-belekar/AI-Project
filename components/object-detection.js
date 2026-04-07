"use client";

import React, { useEffect, useState } from "react";

const WebcamView = () => {
  const [intrusion, setIntrusion] = useState({
    detected: false,
    time: null,
    distance: null,
  });

  // Poll intrusion status
  // Poll intrusion status
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = () => {
      console.log("✅ WebSocket Connected");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // 1. Listen for the Intrusion Alert
      if (data.type === "intrusion") {
        setIntrusion({
          detected: true,
          time: data.time,
          distance: data.distance || null,
        });
      }
      // 2. Listen for the Reset Confirmation
      else if (data.type === "reset") {
        setIntrusion({
          detected: false,
          time: null,
          distance: null,
        });
      }
    };

    ws.onclose = () => {
      console.log("❌ WebSocket Disconnected");
    };

    return () => {
      ws.close();
    };
  }, []);

  // NEW: Function to unfreeze the backend
  const handleReset = async () => {
    try {
      const response = await fetch("http://localhost:8000/reset");
      if (response.ok) {
        // Optimistically clear the UI alert immediately
        setIntrusion({ detected: false, time: null, distance: null });
      } else {
        console.error("Failed to reset the surveillance system.");
      }
    } catch (error) {
      console.error("Error communicating with backend:", error);
    }
  };

  return (
    <div className="mt-8 flex flex-col items-center">
      <h1 className="text-2xl font-bold mb-4">🌲 Forest Surveillance System</h1>

      {/* Live Stream From Backend */}
      <div className="border-4 border-gray-800 rounded-lg overflow-hidden shadow-lg">
        {/* We use a cache-busting trick (?t=...) occasionally if browsers aggressively cache frozen MJPEG streams, but standard src usually works fine */}
        <img
          src="http://localhost:8000/video"
          alt="Live Surveillance Feed"
          className="w-full lg:h-[720px]"
        />
      </div>

      {/* Status Panel & Controls */}
      <div className="mt-6 w-full max-w-xl">
        {intrusion.detected ? (
          <div className="flex flex-col gap-4">
            {/* Alert Box */}
            <div className="bg-red-600 text-white p-4 rounded-lg animate-pulse text-center">
              🚨 HUMAN INTRUSION DETECTED
              <br />
              <span className="text-sm">
                {intrusion.time}
                {intrusion.distance && ` | Distance: ${intrusion.distance}`}
              </span>
            </div>

            {/* NEW: Reset Button */}
            <button
              onClick={handleReset}
              className="w-full bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors shadow-md flex items-center justify-center gap-2"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                  clipRule="evenodd"
                />
              </svg>
              Resume Surveillance
            </button>
          </div>
        ) : (
          <div className="bg-green-600 text-white p-4 rounded-lg text-center shadow-md">
            ✅ Forest Safe – No Human Detected
          </div>
        )}
      </div>
    </div>
  );
};

export default WebcamView;
