package io.github.young1lin.dto;

import java.io.Serializable;
import java.util.HashMap;
import java.util.Map;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class CallToolJSONRPCRequest implements Serializable {

    @Builder.Default
    private String jsonrpc = "2.0";

    @Builder.Default
    private String method = "tools/call";

    private Map<String, Object> params;

    private String id;

    public CallToolJSONRPCRequest(String name, String id, Map<String, Object> arguments) {
        this.jsonrpc = "2.0";
        this.method = "tools/call";
        this.id = id;

        Map<String, Object> paramsMap = new HashMap<>();
        paramsMap.put("name", name);
        if (arguments != null) {
            paramsMap.put("arguments", arguments);
        }
        this.params = paramsMap;
    }
}

