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
public class ListToolsJSONRPCRequest implements Serializable {

    @Builder.Default
    private String jsonrpc = "2.0";

    @Builder.Default
    private String method = "tools/list";

    private Map<String, Object> params;

    private String id;

    public ListToolsJSONRPCRequest(String id, String cursor) {
        this.jsonrpc = "2.0";
        this.method = "tools/list";
        this.id = id;

        Map<String, Object> paramsMap = new HashMap<>();
        if (cursor != null) {
            paramsMap.put("cursor", cursor);
        }
        this.params = paramsMap.isEmpty() ? null : paramsMap;
    }
}

