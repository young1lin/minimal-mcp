package io.github.young1lin.dto;

import java.io.Serializable;
import java.util.Map;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class InitializeJSONRPCRequest implements Serializable {

    @Builder.Default
    private String jsonrpc = "2.0";

    @Builder.Default
    private String method = "initialize";

    private Map<String, Object> params;

    private String id;

    // public InitializeJSONRPCRequest() {
    //     this.jsonrpc = "2.0";
    //     this.method = "initialize";

    //     Map<String, Object> paramsMap = new HashMap<>();
    //     paramsMap.put("protocolVersion", "2024-11-05");

    //     Map<String, Object> capabilities = new HashMap<>();
    //     Map<String, Boolean> roots = new HashMap<>();
    //     roots.put("listChanged", true);
    //     capabilities.put("roots", roots);
    //     paramsMap.put("capabilities", capabilities);

    //     Map<String, Object> clientInfo = new HashMap<>();
    //     clientInfo.put("name", "Fake-Cline");
    //     clientInfo.put("version", "0.0.1-SNAPSHOT");
    //     paramsMap.put("clientInfo", clientInfo);

    //     this.params = paramsMap;
    // }
}

