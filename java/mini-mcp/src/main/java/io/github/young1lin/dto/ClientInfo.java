package io.github.young1lin.dto;

import java.io.Serializable;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class ClientInfo implements Serializable {

    @Builder.Default
    private String name = "Fake-Cline";

    @Builder.Default
    private String version = "0.0.1-SNAPSHOT";

    private String title;
}

