package io.github.young1lin.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.Map;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class ToolDefinition implements Serializable {

    private String name;

    private String description;

    private ToolInputSchema inputSchema;

    private String title;

    private ToolOutputSchema outputSchema;

    private Map<String, Object> annotations;
}

