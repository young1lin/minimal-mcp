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
public class ServerInfo implements Serializable {

    @Builder.Default
    private String name = "Fake-Weather-Server";

    @Builder.Default
    private String version = "0.0.1-SNAPSHOT";

    private String title;
}

