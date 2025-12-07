package io.github.young1lin.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.HashMap;
import java.util.Map;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class InitializeJSONRPCResult implements Serializable {

    private String id;

    private Object result;

    private JSONRPCError error;

    @Builder.Default
    private String jsonrpc = "2.0";

    public InitializeJSONRPCResult(String id, boolean isError) {
        this.id = id;
        this.jsonrpc = "2.0";

        if (isError) {
            this.result = null;
            this.error = JSONRPCError.builder()
                    .code(-1)
                    .message("Initialize error")
                    .build();
        } else {
            Capabilities capabilities = Capabilities.builder()
                    .tools(Map.of("listChanged", true))
                    .logging(Map.of("listChanged", false))
                    .prompts(Map.of("listChanged", false))
                    .resources(Map.of("subscribe", false, "listChanged", false))
                    .completions(Map.of("listChanged", false))
                    .experimental(Map.of("listChanged", false))
                    .build();

            Map<String, Object> resultMap = new HashMap<>();
            resultMap.put("protocolVersion", "2024-11-05");
            resultMap.put("capabilities", capabilities);
            resultMap.put("serverInfo", ServerInfo.builder().build());
            resultMap.put("instructions", "Fake-Weather MCP Server");

            this.result = resultMap;
            this.error = null;
        }
    }

    public boolean isError() {
        return this.error != null;
    }
}

