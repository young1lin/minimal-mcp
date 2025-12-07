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
public class Capabilities implements Serializable {

    private Map<String, Boolean> roots;

    private Map<String, Object> sampling;

    private Map<String, Object> elicitation;

    private Map<String, Boolean> logging;

    private Map<String, Boolean> prompts;

    private Map<String, Boolean> resources;

    private Map<String, Boolean> tools;

    private Map<String, Boolean> completions;

    private Map<String, Boolean> experimental;
}

