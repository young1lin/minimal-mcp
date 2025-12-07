package io.github.young1lin.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.io.Serializable;


@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class JSONRPCResponse implements Serializable {

    @Builder.Default
    private String jsonrpc = "2.0";

    private String id;

    private Object result;

    private JSONRPCError error;

    public boolean isError() {
        return this.error != null;
    }
}
