/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { type FunctionDeclaration, SchemaType } from "@google/generative-ai";
import { useEffect, useRef, useState, memo } from "react";
import vegaEmbed from "vega-embed";
import { useLiveAPIContext } from "../../contexts/LiveAPIContext";
import { ToolCall } from "../../multimodal-live-types";
import { sendEmailDeclaration } from "../../lib/tool-declarations";

const declaration: FunctionDeclaration = {
  name: "render_altair",
  description: "Displays an altair graph in json format.",
  parameters: {
    type: SchemaType.OBJECT,
    properties: {
      json_graph: {
        type: SchemaType.STRING,
        description:
          "JSON STRING representation of the graph to render. Must be a string, not a json object",
      },
    },
    required: ["json_graph"],
  },
};

function AltairComponent() {
  const [jsonString, setJSONString] = useState<string>("");
  const { client, setConfig } = useLiveAPIContext();

  useEffect(() => {
      setConfig({
        model: "models/gemini-2.0-flash-exp",
        generationConfig: {
          temperature: 0.7,
          topK: 40,
          topP: 0.95,
          maxOutputTokens: 2048,
        },
        systemInstruction: {
          parts: [
            {
              text: `I am an advanced AI model created by Critical Future, a leading technology company specializing in cutting-edge AI solutions. 
  
  I excel in data visualization and analytics, leveraging my expertise in Altair/Vega-Lite charts to create insightful visual representations of data.
  
  As a Critical Future AI, I prioritize:
  - Innovation in data presentation
  - Clear communication through visuals
  - Professional-grade visualizations
  - Data-driven insights
  - User-centric design principles
  
  When creating visualizations, I:
  - Use clear, descriptive titles and labels
  - Apply Critical Future's professional color schemes
  - Include interactive elements for deeper data exploration
  - Provide meaningful axis labels and legends
  - Generate representative sample data when needed
  - Always utilize the render_altair function
  - Handle edge cases and null values professionally
  
  If any visualization encounters issues, I provide constructive solutions and alternatives, maintaining Critical Future's commitment to excellence in AI services.
  Additionally, I have access to the send_email tool which allows me to send emails by specifying the recipient, subject, body, and sender.`,
            },
          ],
        },
        tools: [
          { googleSearch: {} },
          { functionDeclarations: [declaration, sendEmailDeclaration] },
        ],
      });
    }, [setConfig]);

  useEffect(() => {
    const onToolCall = (toolCall: ToolCall) => {
      console.log(`got toolcall`, toolCall);
      const fc = toolCall.functionCalls.find(
        (fc) => fc.name === declaration.name,
      );
      if (fc) {
        const str = (fc.args as any).json_graph;
        setJSONString(str);
      }
      // send data for the response of your tool call
      // in this case Im just saying it was successful
      if (toolCall.functionCalls.length) {
        setTimeout(
          () =>
            client.sendToolResponse({
              functionResponses: toolCall.functionCalls.map((fc) => ({
                response: { output: { success: true } },
                id: fc.id,
              })),
            }),
          200,
        );
      }
    };
    client.on("toolcall", onToolCall);
    return () => {
      client.off("toolcall", onToolCall);
    };
  }, [client]);

  const embedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
      if (embedRef.current && jsonString) {
        try {
          const spec = JSON.parse(jsonString);
          vegaEmbed(embedRef.current, spec, {
            actions: true,
            theme: 'dark',
            renderer: 'svg',
            downloadFileName: 'visualization',
            tooltip: { theme: 'dark' },
          }).catch(error => {
            console.error('Vega-Embed Error:', error);
            client.send([{ 
              text: `The visualization failed to render with error: ${error.message}. Please try to fix the specification or suggest an alternative approach.`
            }]);
          });
        } catch (error) {
          console.error('JSON Parse Error:', error);
          client.send([{ 
            text: `Failed to parse the visualization JSON. Please provide a valid specification.`
          }]);
        }
      }
    }, [embedRef, jsonString, client]);
  return <div className="vega-embed" ref={embedRef} />;
}

export const Altair = memo(AltairComponent);
