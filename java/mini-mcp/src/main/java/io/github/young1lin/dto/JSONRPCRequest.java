package io.github.young1lin.dto;

import java.io.Serializable;
import java.util.Map;
import java.util.UUID;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class JSONRPCRequest implements Serializable {

    @Builder.Default
    private String jsonrpc = "2.0";

    private String method;

    private Map<String, Object> params;

    private String id;

    public void generateIdIfNone() {
        if (this.id == null || this.id.isEmpty()) {
            this.id = UUID.randomUUID().toString();
        }
    }
}
