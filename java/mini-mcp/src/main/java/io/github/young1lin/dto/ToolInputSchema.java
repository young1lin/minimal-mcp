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
public class ToolInputSchema implements Serializable {

    @Builder.Default
    private String type = "object";

    private Map<String, ToolParameterProperty> properties;

    private java.util.List<String> required;
}

