package io.github.young1lin.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class ListToolsJSONRPCResult implements Serializable {

    private String id;

    private Object result;

    private JSONRPCError error;

    @Builder.Default
    private String jsonrpc = "2.0";

    public ListToolsJSONRPCResult(String id, List<ToolDefinition> tools, String nextCursor, boolean isError) {
        this.id = id;
        this.jsonrpc = "2.0";

        if (isError) {
            this.error = JSONRPCError.builder()
                    .code(-1)
                    .message("Failed to list tools")
                    .build();
            this.result = null;
        } else {
            if (tools == null) {
                tools = new ArrayList<>();
            }

            Map<String, Object> resultMap = new HashMap<>();
            resultMap.put("tools", tools);
            if (nextCursor != null) {
                resultMap.put("nextCursor", nextCursor);
            }

            this.result = resultMap;
            this.error = null;
        }
    }

    public boolean isError() {
        return this.error != null;
    }
}

