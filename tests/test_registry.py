import unittest

from demand_radar.contracts import (
    Capability,
    CommentRequest,
    HealthReport,
    ProviderDescriptor,
    ProviderRole,
    PublishResult,
    PublisherProvider,
)
from demand_radar.errors import UnsupportedCapabilityError
from demand_radar.registry import ProviderRegistry


class CommentOnlyPublisher(PublisherProvider):
    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            name="comments_only",
            role=ProviderRole.PUBLISHER,
            capabilities=frozenset({Capability.POST_COMMENT}),
        )

    def health(self) -> HealthReport:
        return HealthReport(True, "ready")

    def post_comment(self, request: CommentRequest) -> PublishResult:
        return PublishResult(
            provider=self.descriptor.name,
            action=Capability.POST_COMMENT,
            success=True,
            external_id="new-comment",
        )


class RegistryTests(unittest.TestCase):
    def test_partial_publisher_capabilities_are_supported(self) -> None:
        registry = ProviderRegistry()
        registry.register_publisher(CommentOnlyPublisher())

        provider = registry.publisher("comments_only", Capability.POST_COMMENT)
        result = provider.post_comment(CommentRequest("note-1", "内容"))

        self.assertTrue(result.success)
        with self.assertRaises(UnsupportedCapabilityError):
            registry.publisher("comments_only", Capability.PUBLISH_NOTE)


if __name__ == "__main__":
    unittest.main()
