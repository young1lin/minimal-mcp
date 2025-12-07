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
public class CallToolJSONRPCResult implements Serializable {

    private String id;

    private Object result;

    private JSONRPCError error;

    @Builder.Default
    private String jsonrpc = "2.0";

    public CallToolJSONRPCResult(String id, List<ToolContent> content, boolean isError, String errorMessage) {
        this.id = id;
        this.jsonrpc = "2.0";

        if (isError) {
            this.error = JSONRPCError.builder()
                    .code(-1)
                    .message(errorMessage != null ? errorMessage : "Tool execution failed")
                    .build();
            this.result = null;
        } else {
            Map<String, Object> resultMap = new HashMap<>();
            if (content == null) {
                content = new ArrayList<>();
            }
            resultMap.put("content", content);
            resultMap.put("isError", false);

            this.result = resultMap;
            this.error = null;
        }
    }

    public boolean isError() {
        return this.error != null;
    }
}

