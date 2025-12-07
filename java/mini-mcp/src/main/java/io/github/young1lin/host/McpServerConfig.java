package io.github.young1lin.host;

import java.util.Collections;
import java.util.List;
import java.util.Map;

import lombok.Data;

@Data
public class McpServerConfig {

    /**
     * stdio or http, null is stdio
     */
    // fk jakarta @Nullable
    private String type;

    private String command;

    private List<String> args = Collections.emptyList();

    private Map<String, String> env = Collections.emptyMap();

}
